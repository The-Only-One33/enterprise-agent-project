#!/usr/bin/env python3
"""创建 conversations / messages 表。在 backend 目录执行: python scripts/init_conversation_tables.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 允许在 backend 目录直接运行脚本
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def main() -> int:
    from app.core.database import engine
    from app.core.base import Base
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables conversations / messages are ready (create_all).")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
