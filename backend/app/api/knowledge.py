"""
知识库API - 对接 RAG 向量索引
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app.services.rag_service import get_rag_service

router = APIRouter()

DEFAULT_TENANT = "TENANT_DEFAULT"


class DocumentCreate(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []
    source_type: Optional[str] = "manual"
    tenant_id: Optional[str] = DEFAULT_TENANT
    doc_type: Optional[str] = "manual"
    category: Optional[str] = ""


class DocumentIndexResponse(BaseModel):
    doc_id: str
    chunk_count: int
    chunk_ids: List[str]
    title: str


@router.get("/")
async def list_documents(keyword: Optional[str] = None):
    """列出向量库中的父文档（按 doc_id 聚合）。"""
    rag = get_rag_service()
    try:
        data = rag.vectorstore.get(include=["metadatas"])
        metas = data.get("metadatas") or []
        seen: dict = {}
        for meta in metas:
            if not meta:
                continue
            doc_id = meta.get("doc_id")
            if not doc_id or doc_id in seen:
                continue
            title = meta.get("title") or meta.get("parent_title") or doc_id
            if keyword and keyword not in title:
                continue
            seen[doc_id] = {
                "doc_id": doc_id,
                "title": title,
                "doc_type": meta.get("doc_type"),
                "category": meta.get("category"),
                "tenant_id": meta.get("tenant_id"),
            }
        docs = list(seen.values())
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def index_stats():
    rag = get_rag_service()
    return {"chunk_count": rag.get_collection_count()}


@router.get("/search/")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    tenant_id: str = DEFAULT_TENANT,
    top_k: int = 5,
):
    """调试接口：直接测试 RAG 检索。"""
    rag = get_rag_service()
    results = await rag.similarity_search(
        query=q,
        tenant_id=tenant_id,
        top_k=top_k,
        enable_optimization=False,
    )
    return {"query": q, "results": results}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """按 doc_id 拼接该文档全部 chunk 内容。"""
    rag = get_rag_service()
    try:
        data = rag.vectorstore.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        if not docs:
            raise HTTPException(status_code=404, detail="文档不存在")
        pairs = sorted(
            zip(docs, metas),
            key=lambda x: (x[1] or {}).get("chunk_index", 0),
        )
        content = "\n\n".join(d for d, _ in pairs)
        meta = pairs[0][1] or {}
        return {
            "doc_id": doc_id,
            "title": meta.get("title") or meta.get("parent_title"),
            "content": content,
            "chunk_count": len(docs),
            "metadata": meta,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", status_code=201, response_model=DocumentIndexResponse)
async def create_document(request: DocumentCreate):
    """创建知识文档并写入 RAG 索引（自动分块）。"""
    rag = get_rag_service()
    metadata = {
        "tenant_id": request.tenant_id or DEFAULT_TENANT,
        "title": request.title,
        "doc_type": request.doc_type or request.source_type,
        "source_type": request.source_type,
    }
    if request.category and request.category.strip():
        metadata["category"] = request.category.strip()
    tag_list = [t.strip() for t in (request.tags or []) if t and str(t).strip()]
    if tag_list:
        metadata["tags"] = tag_list
    try:
        result = await rag.add_document(content=request.content, metadata=metadata)
        return DocumentIndexResponse(
            doc_id=result["doc_id"],
            chunk_count=result["chunk_count"],
            chunk_ids=result["chunk_ids"],
            title=request.title,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    rag = get_rag_service()
    ok = await rag.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在或已删除")
