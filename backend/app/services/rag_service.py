"""
RAG向量检索服务 - 基于 Chroma 向量数据库

功能说明：
- 使用 Chroma 本地向量数据库存储知识文档（按 chunk 索引）
- 支持持久化存储，重启不丢失
- 支持租户隔离
- 支持 Query 优化（rewrite + expand）
- 支持 BM25 + 向量混合检索 + 候选重排

索引策略：
- 写入时按 Markdown 标题 / 递归字符分块
- 每 chunk 携带 doc_id、chunk_id、tenant_id 等元数据
- 增删文档后自动重建 BM25 索引
"""
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
import os
import uuid
import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import DashScopeEmbeddings

from app.config import get_settings
from app.core.logging import get_logger
from app.services.rag.query_optimizer import get_query_optimizer
from app.services.rag.chunker import chunk_document, DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from app.services.rag.reranker import get_reranker

logger = get_logger(__name__)
settings = get_settings()

CHROMA_PERSIST_DIR = "./data/chroma_db"
BM25_ALPHA = 0.3
RERANK_CANDIDATE_MULTIPLIER = 6  # 粗排候选数 = top_k * 此系数

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
RAG_DOCS_DIR = os.path.join(_BACKEND_ROOT, "data", "rag", "docs")


def _sanitize_chroma_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma 要求 list 类型 metadata 非空；None / 空列表 / 空字符串不入库。"""
    cleaned: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            cleaned[key] = value
        elif isinstance(value, str) and not value.strip():
            continue
        else:
            cleaned[key] = value
    return cleaned


class BM25Retriever:
    """BM25 检索器，文档列表与 Chroma chunk 一一对应，支持租户过滤。"""

    def __init__(self, documents: List[Document]):
        try:
            from rank_bm25 import BM25Okapi

            self.enabled = True
            self._documents = documents
            tokenized_docs = [self._tokenize(doc.page_content) for doc in documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        except ImportError:
            logger.warning("rank_bm25 not installed, BM25 disabled")
            self.enabled = False
            self._documents = []

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+|\d+", text.lower())

    def search(
        self,
        query: str,
        k: int = 10,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[int, float]]:
        if not self.enabled:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        results: List[Tuple[int, float]] = []
        for i in ranked:
            if scores[i] <= 0 and results:
                break
            if tenant_id:
                doc_tenant = self._documents[i].metadata.get("tenant_id")
                if doc_tenant and doc_tenant != tenant_id:
                    continue
            results.append((i, scores[i]))
            if len(results) >= k:
                break
        return results


class RAGService:
    """RAG检索服务 - 基于 Chroma，chunk 级索引。"""

    def __init__(self):
        api_key = settings.openai_api_key
        if api_key and not os.environ.get("DASHSCOPE_API_KEY"):
            os.environ["DASHSCOPE_API_KEY"] = api_key

        self.embeddings = DashScopeEmbeddings(
            dashscope_api_key=api_key,
            model=settings.openai_embedding_model or "text-embedding-v2",
        )

        self.vectorstore = Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowledge_docs",
        )

        if self.vectorstore._collection.count() == 0:
            self._load_sample_data()

        self._bm25: Optional[BM25Retriever] = None
        self._bm25_docs: List[Document] = []
        self._rebuild_bm25()

        logger.info("rag_service_initialized", persist_dir=CHROMA_PERSIST_DIR)

    def _rebuild_bm25(self):
        """从 Chroma 全量同步 BM25 索引（增删文档后调用）。"""
        try:
            all_data = self.vectorstore.get(include=["documents", "metadatas"])
            if not all_data or not all_data.get("documents"):
                self._bm25_docs = []
                self._bm25 = BM25Retriever([])
                return

            self._bm25_docs = [
                Document(
                    page_content=doc,
                    metadata=meta or {},
                )
                for doc, meta in zip(
                    all_data["documents"],
                    all_data.get("metadatas") or [{}] * len(all_data["documents"]),
                )
            ]
            self._bm25 = BM25Retriever(self._bm25_docs)
            logger.info("bm25_rebuilt", doc_count=len(self._bm25_docs))
        except Exception as e:
            logger.warning(f"BM25 rebuild failed: {e}")

    def _hybrid_search(
        self,
        query: str,
        k: int = 10,
        tenant_id: Optional[str] = None,
    ) -> List[Tuple[Document, float]]:
        chroma_filter = {"tenant_id": tenant_id} if tenant_id else None

        if self._bm25 is None or not self._bm25.enabled:
            return self.vectorstore.similarity_search_with_score(
                query=query, k=k, filter=chroma_filter
            )

        vector_results = self.vectorstore.similarity_search_with_score(
            query=query, k=k * 2, filter=chroma_filter
        )
        bm25_results = self._bm25.search(query, k=k * 2, tenant_id=tenant_id)

        max_vector_score = max((s for _, s in vector_results), default=1.0) or 1.0
        max_bm25_score = max((s for _, s in bm25_results), default=1.0) or 1.0

        fused: Dict[str, Tuple[Document, float]] = {}

        for doc, score in vector_results:
            key = doc.metadata.get("chunk_id") or doc.metadata.get("doc_id", id(doc))
            fused[key] = (doc, score / max_vector_score)

        for idx, bm25_score in bm25_results:
            doc = self._bm25_docs[idx]
            key = doc.metadata.get("chunk_id") or doc.metadata.get("doc_id", idx)
            norm_bm25 = bm25_score / max_bm25_score
            if key in fused:
                old_doc, vector_score = fused[key]
                fused_score = (1 - BM25_ALPHA) * vector_score + BM25_ALPHA * norm_bm25
                fused[key] = (old_doc, fused_score)
            else:
                fused[key] = (doc, BM25_ALPHA * norm_bm25)

        sorted_results = sorted(fused.values(), key=lambda x: x[1], reverse=True)
        return sorted_results[:k]

    def _load_sample_data(self):
        """加载示例知识（首次启动，按 chunk 写入）。"""
        sample_docs = [
            {
                "page_content": "【任务创建流程】\n1. 点击「新建任务」按钮\n2. 填写任务名称、描述\n3. 选择负责人和参与人\n4. 设置截止日期\n5. 点击确认创建",
                "metadata": {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": "操作指南",
                    "title": "如何创建任务",
                    "category": "任务管理",
                },
            },
            {
                "page_content": "【任务打分标准】\n优秀(90-100分)：超出预期完成\n良好(80-89分)：按时按质完成\n合格(60-79分)：基本达到要求\n待改进(<60分)：需要返工",
                "metadata": {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": "制度文件",
                    "title": "任务评分标准",
                    "category": "绩效考核",
                },
            },
            {
                "page_content": "【项目管理制度】\n1. 项目立项需填写项目计划书\n2. 项目成员由项目经理分配\n3. 每周需更新项目进度\n4. 项目验收需所有里程碑达成",
                "metadata": {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": "制度文件",
                    "title": "项目管理规范",
                    "category": "项目管理",
                },
            },
            {
                "page_content": "【常见问题FAQ】\nQ: 如何修改任务负责人？\nA: 进入任务详情页，点击负责人头像即可更换\n\nQ: 任务超时了怎么办？\nA: 及时与项目经理沟通，重新评估工期",
                "metadata": {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": "FAQ",
                    "title": "常见问题解答",
                    "category": "帮助中心",
                },
            },
            {
                "page_content": "【目标管理(OKR)】\nO: 定义目标（Objective）\nKR: 关键结果（Key Results）\n周期：季度/年度\n复盘：每周期末进行自评和上级评价",
                "metadata": {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": "知识科普",
                    "title": "OKR目标管理法",
                    "category": "目标管理",
                },
            },
        ]

        try:
            all_chunks: List[Document] = []
            all_ids: List[str] = []
            for i, sample in enumerate(sample_docs):
                doc_id = f"doc_sample_{i}"
                meta = {**sample["metadata"], "doc_id": doc_id}
                chunks = chunk_document(sample["page_content"], meta)
                for c in chunks:
                    all_chunks.append(c)
                    all_ids.append(c.metadata["chunk_id"])

            if all_chunks:
                self.vectorstore.add_documents(documents=all_chunks, ids=all_ids)
                logger.info("sample_knowledge_loaded", chunk_count=len(all_chunks))
        except Exception as e:
            logger.error(f"Failed to load sample data: {e}")

        self._load_bundled_rag_docs()

    def _load_bundled_rag_docs(self):
        """加载 data/rag/docs 下的内置知识（如周报规范）。"""
        bundled = [
            {
                "filename": "weekly_report_writing_guide.md",
                "doc_id": "doc_weekly_report_guide",
                "title": "员工周报撰写规范与模板说明",
                "doc_type": "制度文件",
                "category": "周报",
            },
        ]
        for item in bundled:
            path = os.path.join(RAG_DOCS_DIR, item["filename"])
            if not os.path.isfile(path):
                continue
            try:
                content = Path(path).read_text(encoding="utf-8")
                meta = {
                    "tenant_id": "TENANT_DEFAULT",
                    "doc_type": item["doc_type"],
                    "title": item["title"],
                    "category": item["category"],
                    "doc_id": item["doc_id"],
                }
                chunks = chunk_document(content, meta)
                if not chunks:
                    continue
                ids = [c.metadata["chunk_id"] for c in chunks]
                for c in chunks:
                    c.metadata = _sanitize_chroma_metadata(c.metadata)
                self.vectorstore.add_documents(documents=chunks, ids=ids)
                logger.info(
                    "bundled_rag_doc_loaded",
                    doc_id=item["doc_id"],
                    chunk_count=len(chunks),
                )
            except Exception as e:
                logger.warning(
                    "bundled_rag_doc_load_failed",
                    doc_id=item.get("doc_id"),
                    error=str(e),
                )

    async def _delete_chunks_by_doc_id(self, doc_id: str) -> int:
        """删除某父文档下的全部 chunk。"""
        try:
            existing = self.vectorstore.get(where={"doc_id": doc_id})
            ids = existing.get("ids") or []
            if ids:
                self.vectorstore.delete(ids=ids)
            return len(ids)
        except Exception as e:
            logger.warning("delete_chunks_failed", doc_id=doc_id, error=str(e))
            return 0

    async def similarity_search(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 5,
        enable_optimization: bool = True,
        use_hybrid: bool = True,
        enable_rerank: bool = True,
        history: Optional[List[Dict[str, str]]] = None,
        resolved_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        语义相似度检索 - chunk 级检索（Query 优化 + 混合检索 + 重排）

        history: 多轮对话 [{role, content}]，用于 contextualize（若 resolved_query 未提供）
        resolved_query: 意图阶段已解析的 standalone query，避免重复 LLM
        """
        logger.info("rag_search_started", query=query[:50], tenant_id=tenant_id)

        try:
            optimized = None
            if enable_optimization:
                optimizer = get_query_optimizer()
                optimized = await optimizer.optimize(
                    query,
                    strategy="expand",
                    history=history,
                    resolved_query=resolved_query,
                )
                final_queries = optimized["final_queries"]
                logger.info(
                    "query_optimization_applied",
                    original=query[:30],
                    resolved=optimized.get("resolved", query)[:30],
                    rewritten=optimized["rewritten"][:30],
                    query_count=len(final_queries),
                )
            else:
                final_queries = [query]

            recall_k = top_k * RERANK_CANDIDATE_MULTIPLIER if enable_rerank else top_k * 2
            all_results: Dict[str, Dict[str, Any]] = {}

            for search_query in final_queries:
                if use_hybrid and self._bm25 and self._bm25.enabled:
                    hits = self._hybrid_search(
                        query=search_query, k=recall_k, tenant_id=tenant_id
                    )
                else:
                    hits = self.vectorstore.similarity_search_with_score(
                        query=search_query,
                        k=recall_k,
                        filter={"tenant_id": tenant_id},
                    )

                for doc, score in hits:
                    chunk_key = doc.metadata.get("chunk_id", doc.page_content[:50])

                    if chunk_key not in all_results:
                        all_results[chunk_key] = {
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "max_score": score,
                            "matched_queries": [],
                        }
                    else:
                        all_results[chunk_key]["max_score"] = max(
                            all_results[chunk_key]["max_score"], score
                        )
                    all_results[chunk_key]["matched_queries"].append(search_query[:20])

            # 粗排候选
            candidates = sorted(
                all_results.values(), key=lambda x: x["max_score"], reverse=True
            )[:recall_k]

            # 重排：对粗排候选精排后取 top_k
            if enable_rerank and candidates:
                reranker = get_reranker()
                doc_score_pairs = [
                    (
                        Document(page_content=c["content"], metadata=c["metadata"]),
                        c["max_score"],
                    )
                    for c in candidates
                ]
                reranked = reranker.rerank(query, doc_score_pairs, top_k=top_k)
                key_to_candidate = {
                    c["metadata"].get("chunk_id", c["content"][:50]): c
                    for c in candidates
                }
                final_candidates = []
                for doc, score in reranked:
                    ck = doc.metadata.get("chunk_id", doc.page_content[:50])
                    if ck in key_to_candidate:
                        item = key_to_candidate[ck]
                        item["max_score"] = score
                        final_candidates.append(item)
                candidates = final_candidates
            else:
                candidates = candidates[:top_k]

            results = []
            for i, result in enumerate(candidates):
                meta = result["metadata"]
                results.append({
                    "rank": i + 1,
                    "content": result["content"],
                    "metadata": meta,
                    "similarity_score": round(result["max_score"], 4),
                    "matched_queries": result["matched_queries"],
                    "doc_id": meta.get("doc_id"),
                    "chunk_id": meta.get("chunk_id"),
                    "chunk_index": meta.get("chunk_index"),
                    "parent_title": meta.get("parent_title") or meta.get("title"),
                })

            if optimized:
                results.insert(0, {
                    "type": "optimization_info",
                    "original": query,
                    "resolved": optimized.get("resolved", query),
                    "rewritten": optimized["rewritten"],
                    "expanded": optimized["expanded"],
                    "hyde_doc": optimized.get("hyde_doc", ""),
                    "retrieval_mode": "hybrid" if use_hybrid else "vector_only",
                })

            logger.info("rag_search_completed", results_count=len(results), tenant_id=tenant_id)
            return results

        except Exception as e:
            logger.error("rag_search_failed", error=str(e), tenant_id=tenant_id)
            return []

    async def add_document(
        self,
        content: str,
        metadata: Dict[str, Any],
        document_id: Optional[str] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> Dict[str, Any]:
        """
        添加知识文档（自动分块后写入向量库并同步 BM25）

        Args:
            content: 文档正文
            metadata: 须含 tenant_id；可选 title、doc_type、category 等
            document_id: 父文档 ID，重复传入则先删旧 chunk 再重建
            chunk_size / chunk_overlap: 分块参数

        Returns:
            {"doc_id", "chunk_count", "chunk_ids"}
        """
        if not metadata.get("tenant_id"):
            raise ValueError("metadata 必须包含 tenant_id")

        doc_id = document_id or f"doc_{uuid.uuid4().hex[:12]}"
        metadata = _sanitize_chroma_metadata({**metadata, "doc_id": doc_id})

        await self._delete_chunks_by_doc_id(doc_id)

        chunks = chunk_document(content, metadata, chunk_size, chunk_overlap)
        for chunk in chunks:
            chunk.metadata = _sanitize_chroma_metadata(chunk.metadata)
        if not chunks:
            raise ValueError("文档内容为空，无法分块")

        ids = [c.metadata["chunk_id"] for c in chunks]
        self.vectorstore.add_documents(documents=chunks, ids=ids)
        self._rebuild_bm25()

        logger.info(
            "document_indexed",
            doc_id=doc_id,
            chunk_count=len(chunks),
            tenant_id=metadata.get("tenant_id"),
        )
        return {
            "doc_id": doc_id,
            "chunk_count": len(chunks),
            "chunk_ids": ids,
        }

    async def delete_document(self, document_id: str) -> bool:
        """删除父文档及其全部 chunk，并同步 BM25。"""
        try:
            deleted = await self._delete_chunks_by_doc_id(document_id)
            if deleted > 0:
                self._rebuild_bm25()
            logger.info("document_deleted", doc_id=document_id, chunks_deleted=deleted)
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    async def find_similar_tasks(
        self,
        task_description: str,
        tenant_id: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        return await self.similarity_search(
            query=task_description,
            tenant_id=tenant_id,
            top_k=top_k,
            enable_optimization=False,
        )

    def get_collection_count(self) -> int:
        return self.vectorstore._collection.count()


@lru_cache()
def get_rag_service() -> RAGService:
    return RAGService()
