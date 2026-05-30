#!/usr/bin/env python3
"""为已有 token_usage_log 表增加 stage 列。在 backend 目录执行: python scripts/migrate_token_usage_stage.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def main() -> int:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "enterprise_agent")

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'token_usage_log' AND COLUMN_NAME = 'stage'
                """,
                (database,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "ALTER TABLE token_usage_log "
                    "ADD COLUMN stage VARCHAR(32) NOT NULL DEFAULT 'answer' AFTER intent"
                )
                cur.execute(
                    "CREATE INDEX ix_token_usage_log_stage ON token_usage_log (stage)"
                )
                print("Added column token_usage_log.stage")
            else:
                print("Column token_usage_log.stage already exists")
        conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
