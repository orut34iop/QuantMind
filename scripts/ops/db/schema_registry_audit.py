#!/usr/bin/env python3
"""
Schema registry audit tool.

用途：
1. 打印已归口 schema 与表清单；
2. 检测归口范围内是否存在重复表名（跨 metadata 冲突风险）；
3. 可选连接数据库检查“缺失表”（registry 定义但数据库中不存在）。
"""

from __future__ import annotations
from backend.shared.schema_registry import (
    detect_duplicate_tables,
    load_registered_schemas,
    registry_summary,
)

import argparse
import asyncio
import os
import sys
from typing import Set

from sqlalchemy import inspect

# 允许在仓库根目录直接执行 `python backend/scripts/schema_registry_audit.py`
REPO_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit unified schema registry")
    parser.add_argument(
        "--schema",
        action="append",
        dest="schemas",
        help="仅审计指定 schema key（可多次传入）",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="检查数据库是否缺失 registry 中的表",
    )
    return parser.parse_args()


async def _check_db_missing_tables(schema_keys: list[str] | None) -> list[str]:
    from backend.shared.database_manager_v2 import (
        close_database,
        get_db_manager,
        init_database,
    )

    await init_database()
    try:
        engine = get_db_manager()._master_engine
        if engine is None:
            raise RuntimeError("Database engine not initialized")
        expected: Set[str] = set()
        for schema in load_registered_schemas(schema_keys):
            expected.update(schema.metadata.tables.keys())

        async with engine.connect() as conn:
            existing = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names())
            )
        return sorted(expected - existing)
    finally:
        await close_database()


def main() -> int:
    args = _parse_args()
    schema_keys = args.schemas if args.schemas else None

    print("=== Unified Schema Registry Summary ===")
    for row in registry_summary(schema_keys):
        print(f"- {row['key']} ({row['service']}): {row['table_count']} tables")

    duplicates = detect_duplicate_tables(schema_keys)
    if duplicates:
        print("\n[ERROR] Duplicate table names detected:")
        for table_name, owners in sorted(duplicates.items()):
            print(f"  - {table_name}: {', '.join(owners)}")
        return 2

    if args.check_db:
        missing = asyncio.run(_check_db_missing_tables(schema_keys))
        if missing:
            print("\n[ERROR] Missing tables in database:")
            for table_name in missing:
                print(f"  - {table_name}")
            return 3

    print("\n[OK] Schema registry audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
