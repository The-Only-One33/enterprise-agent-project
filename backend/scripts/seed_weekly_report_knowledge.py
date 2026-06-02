#!/usr/bin/env python3
"""
将《员工周报撰写规范》写入 Chroma 向量库。

用法（在 backend 目录）:
  PYTHONPATH=. python scripts/seed_weekly_report_knowledge.py

已有向量库时也可重复执行（同 doc_id 会先删后建）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

DOC_ID = "doc_weekly_report_guide"
GUIDE_PATH = ROOT / "data" / "rag" / "docs" / "weekly_report_writing_guide.md"
DEFAULT_TENANT = "TENANT_DEFAULT"


async def main() -> int:
    if not GUIDE_PATH.is_file():
        print(f"Missing guide file: {GUIDE_PATH}")
        return 1

    content = GUIDE_PATH.read_text(encoding="utf-8")
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    result = await rag.add_document(
        content=content,
        metadata={
            "tenant_id": DEFAULT_TENANT,
            "title": "员工周报撰写规范与模板说明",
            "doc_type": "制度文件",
            "category": "周报",
            "tags": "周报,工作总结,执行内容,模板",
        },
        document_id=DOC_ID,
    )
    print(
        f"Indexed weekly report guide: doc_id={result['doc_id']}, "
        f"chunks={result['chunk_count']}"
    )

    # 试检索
    hits = await rag.similarity_search(
        query="周报怎么写 要写哪些项 执行内容",
        tenant_id=DEFAULT_TENANT,
        top_k=3,
        enable_optimization=False,
    )
    print(f"Smoke search returned {len(hits)} hits")
    for i, h in enumerate(hits[:2], 1):
        title = h.get("parent_title") or h.get("metadata", {}).get("title", "")
        print(f"  [{i}] {title} | score={h.get('score', 0):.3f}")
        print(f"      {str(h.get('content', ''))[:120]}...")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
