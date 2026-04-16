#!/usr/bin/env python3
"""
清理“参数优化子回测”污染到普通回测历史的数据。

识别规则：
- 从 qlib_optimization_runs.all_results_json 中提取 all_results[*].metrics.backtest_id
- 与 qlib_backtest_runs 按 (backtest_id, user_id, tenant_id) 精确匹配

默认 dry-run，仅输出统计与样本；传 --apply 才会执行删除。
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import List, Tuple

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

logger = logging.getLogger("cleanup_optimization_backtest_pollution")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_db_connection():
    host = os.getenv("DB_MASTER_HOST", "127.0.0.1")
    port = os.getenv("DB_MASTER_PORT", "5432")
    user = os.getenv("DB_USER", "quantmind")
    password = os.getenv("DB_PASSWORD", "")
    dbname = os.getenv("DB_NAME", "quantmind")
    conn_str = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    return psycopg2.connect(conn_str)


def _base_match_sql() -> str:
    return """
    WITH optimization_backtests AS (
      SELECT DISTINCT
        r.user_id,
        r.tenant_id,
        elem->'metrics'->>'backtest_id' AS backtest_id
      FROM qlib_optimization_runs r
      CROSS JOIN LATERAL jsonb_array_elements(COALESCE(r.all_results_json, '[]'::jsonb)) elem
      WHERE elem ? 'metrics'
        AND (elem->'metrics'->>'backtest_id') IS NOT NULL
    )
    SELECT b.backtest_id, b.user_id, b.tenant_id, b.created_at
    FROM qlib_backtest_runs b
    JOIN optimization_backtests o
      ON b.backtest_id = o.backtest_id
     AND b.user_id = o.user_id
     AND b.tenant_id = o.tenant_id
    """


def find_polluted_rows(conn, tenant_id: str | None, user_id: str | None) -> List[Tuple[str, str, str, str]]:
    conditions = []
    params = []
    if tenant_id:
        conditions.append("b.tenant_id = %s")
        params.append(tenant_id)
    if user_id:
        conditions.append("b.user_id = %s")
        params.append(user_id)

    sql = _base_match_sql()
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY b.created_at DESC"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def delete_polluted_rows(conn, rows: List[Tuple[str, str, str, str]]) -> int:
    if not rows:
        return 0
    ids = [(r[0], r[1], r[2]) for r in rows]
    with conn.cursor() as cur:
        cur.executemany(
            """
            DELETE FROM qlib_backtest_runs
            WHERE backtest_id = %s AND user_id = %s AND tenant_id = %s
            """,
            ids,
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


def main() -> int:
    parser = argparse.ArgumentParser(description="清理参数优化子回测污染到普通回测历史的数据")
    parser.add_argument("--apply", action="store_true", help="执行删除；默认仅 dry-run")
    parser.add_argument("--tenant-id", type=str, default=None, help="仅清理指定 tenant_id")
    parser.add_argument("--user-id", type=str, default=None, help="仅清理指定 user_id")
    parser.add_argument("--sample", type=int, default=10, help="dry-run 样本输出条数")
    args = parser.parse_args()

    conn = None
    try:
        conn = get_db_connection()
        rows = find_polluted_rows(conn, tenant_id=args.tenant_id, user_id=args.user_id)
        count = len(rows)
        logger.info("匹配到疑似污染记录: %s 条", count)
        if count > 0:
            logger.info("样本（最多 %s 条）:", args.sample)
            for backtest_id, user_id, tenant_id, created_at in rows[: max(1, args.sample)]:
                logger.info(
                    "  backtest_id=%s user_id=%s tenant_id=%s created_at=%s",
                    backtest_id,
                    user_id,
                    tenant_id,
                    created_at,
                )

        if not args.apply:
            logger.info("dry-run 完成。若要删除请追加 --apply")
            return 0

        deleted = delete_polluted_rows(conn, rows)
        logger.info("删除完成，共删除 %s 条。", deleted)
        return 0
    except Exception as exc:
        logger.error("执行失败: %s", exc)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

