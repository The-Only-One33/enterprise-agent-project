"""
知识文档分块 - 支持 Markdown 标题感知 + 递归字符切分

策略：
1. 优先按 Markdown 标题（# / ## / ###）切分为语义段
2. 段落仍过长时，用 RecursiveCharacterTextSplitter 二次切分
3. 纯文本无标题时，直接按字符递归切分
"""
from typing import List, Dict, Any
import re

from langchain_core.documents import Document

# 中文友好分隔符（优先级从高到低）
TEXT_SPLITTERS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    ". ",
    " ",
    "",
]

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 80


def _recursive_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """按分隔符优先级递归切分文本。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=TEXT_SPLITTERS,
            length_function=len,
        )
        return splitter.split_text(text)
    except ImportError:
        pass

    # 无 langchain_text_splitters 时的简单滑窗兜底
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - chunk_overlap
    return chunks


def _split_by_markdown_headers(content: str) -> List[str]:
    """按 Markdown 标题切分，保留标题行在段首。"""
    parts = re.split(r"(?=\n#{1,3}\s)", content)
    return [p.strip() for p in parts if p.strip()]


def chunk_document(
    content: str,
    base_metadata: Dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    将整篇文档切分为带元数据的 Document 列表。

    Args:
        content: 文档正文
        base_metadata: 父文档元数据（须含 doc_id、tenant_id 等）
        chunk_size: 单块最大字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        LangChain Document 列表，每块含 chunk_id / chunk_index 等
    """
    doc_id = base_metadata.get("doc_id", "unknown")
    title = base_metadata.get("title", "")

    # 1. 标题感知切段
    if re.search(r"^#{1,3}\s", content, re.MULTILINE) or "【" in content[:200]:
        sections = _split_by_markdown_headers(content)
    else:
        sections = [content.strip()] if content.strip() else []

    # 2. 过长段落二次切分
    raw_chunks: List[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            raw_chunks.append(section)
        else:
            raw_chunks.extend(_recursive_split(section, chunk_size, chunk_overlap))

    if not raw_chunks:
        return []

    # 3. 组装 Document
    documents: List[Document] = []
    for i, chunk_text in enumerate(raw_chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        meta = {
            **base_metadata,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "chunk_index": i,
            "parent_title": title,
            "is_chunk": True,
        }
        documents.append(Document(page_content=chunk_text, metadata=meta))

    return documents
