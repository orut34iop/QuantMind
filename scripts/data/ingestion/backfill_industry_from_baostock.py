#!/usr/bin/env python3
"""使用 baostock 行业数据回填 stock_daily_latest.industry。

默认行为：
- 仅回填 industry 为空/空串/未分类 的记录（不会覆盖已有值）
- 先 dry-run 预览；加 --apply 才真正写库

示例：
  python scripts/backfill_industry_from_baostock.py
  python scripts/backfill_industry_from_baostock.py --apply
  python scripts/backfill_industry_from_baostock.py --apply --overwrite
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import baostock as bs
from sqlalchemy import text

# 兼容从仓库根目录直接运行脚本
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from backend.shared.strategy_storage import get_db
except Exception:
    from shared.strategy_storage import get_db  # type: ignore


def _normalize_code(raw: str) -> str | None:
    """sh.600000 -> SH600000；sz.000001 -> SZ000001。"""
    if not raw:
        return None
    s = raw.strip().lower()
    if "." not in s:
        return None
    market, code = s.split(".", 1)
    market = market.strip()
    code = code.strip()
    if market not in {"sh", "sz", "bj"} or not code:
        return None
    return f"{market.upper()}{code}"


def _normalize_industry(raw: str) -> str:
    """J66货币金融服务 -> 货币金融服务。"""
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"^[A-Z]\d+", "", s)
    return s.strip()


def _max_trade_date_str() -> str | None:
    with get_db() as session:
        d = session.execute(text("SELECT MAX(trade_date) FROM stock_daily_latest")).scalar()
        return d.isoformat() if d else None


def _build_query_dates(explicit_date: str | None) -> list[str]:
    if explicit_date:
        return [explicit_date]

    today = date.today()
    candidates: list[str] = []
    latest = _max_trade_date_str()
    if latest:
        candidates.append(latest)
    candidates.extend(
        [
            today.isoformat(),
            (today - timedelta(days=1)).isoformat(),
            "2025-12-31",
            "2024-12-31",
            "2023-12-31",
        ]
    )

    deduped: list[str] = []
    seen = set()
    for d in candidates:
        if d not in seen:
            deduped.append(d)
            seen.add(d)
    return deduped


def fetch_industry_map(query_date: str | None = None) -> tuple[dict[str, str], str]:
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {login.error_code} {login.error_msg}")

    try:
        dates = _build_query_dates(query_date)
        last_err = None
        for d in dates:
            rs = bs.query_stock_industry(date=d)
            if rs.error_code != "0":
                last_err = f"{rs.error_code} {rs.error_msg}"
                continue

            industry_by_code: dict[str, str] = {}
            while rs.next():
                row = rs.get_row_data()
                # 参考字段：updateDate,code,code_name,industry,industryClassification
                code_raw = row[1] if len(row) > 1 else ""
                industry = _normalize_industry(row[3] if len(row) > 3 else "")
                code = _normalize_code(code_raw)
                if not code or not industry:
                    continue
                # 同一 code 若出现多条，保留首条。
                industry_by_code.setdefault(code, industry)

            if industry_by_code:
                return industry_by_code, d

        raise RuntimeError(f"baostock 未返回可用行业数据，最后错误: {last_err or 'N/A'}")
    finally:
        bs.logout()


def preview(industry_map: dict[str, str], overwrite: bool) -> tuple[int, int, int]:
    with get_db() as session:
        total_rows = session.execute(text("SELECT COUNT(*) FROM stock_daily_latest")).scalar()
        unknown_rows = session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM stock_daily_latest
                WHERE industry IS NULL OR industry = '' OR industry = '未分类'
                """
            )
        ).scalar()

        if overwrite:
            can_update = session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM stock_daily_latest
                    WHERE code = ANY(:codes)
                    """
                ),
                {"codes": list(industry_map.keys())},
            ).scalar()
        else:
            can_update = session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM stock_daily_latest
                    WHERE (industry IS NULL OR industry = '' OR industry = '未分类')
                      AND code = ANY(:codes)
                    """
                ),
                {"codes": list(industry_map.keys())},
            ).scalar()

    return int(total_rows or 0), int(unknown_rows or 0), int(can_update or 0)


def apply_updates(industry_map: dict[str, str], overwrite: bool) -> int:
    updates = [{"code": c, "industry": i} for c, i in industry_map.items()]
    if not updates:
        return 0

    sql = (
        """
        UPDATE stock_daily_latest
        SET industry = :industry
        WHERE code = :code
        """
        if overwrite
        else """
        UPDATE stock_daily_latest
        SET industry = :industry
        WHERE code = :code
          AND (industry IS NULL OR industry = '' OR industry = '未分类')
        """
    )

    with get_db() as session:
        result = session.execute(text(sql), updates)
        session.commit()
        return int(result.rowcount or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="使用 baostock 回填行业字段")
    parser.add_argument("--date", help="查询日期 YYYY-MM-DD；默认由 baostock 使用最新可用数据")
    parser.add_argument("--apply", action="store_true", help="执行写库（默认仅预览）")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有 industry（默认只补空/未分类）")
    args = parser.parse_args()

    query_date = args.date
    if query_date:
        # 轻量日期格式校验
        date.fromisoformat(query_date)

    industry_map, used_date = fetch_industry_map(query_date=query_date)
    total, unknown, can_update = preview(industry_map, overwrite=args.overwrite)

    print("=== Baostock 行业回填预览 ===")
    print(f"使用查询日期: {used_date}")
    print(f"baostock 可用行业映射数: {len(industry_map)}")
    print(f"stock_daily_latest 总行数: {total}")
    print(f"当前未分类行数: {unknown}")
    print(f"本次可更新行数: {can_update}")
    print(f"模式: {'覆盖更新' if args.overwrite else '仅补空/未分类'}")

    # 展示前 20 个行业分布，辅助确认数据质量
    top_counter = Counter(industry_map.values()).most_common(20)
    print("baostock 行业分布 Top20:")
    for name, cnt in top_counter:
        print(f"  {name}: {cnt}")

    if not args.apply:
        print("dry-run 完成；如需执行写库，请添加 --apply")
        return 0

    updated = apply_updates(industry_map, overwrite=args.overwrite)
    print(f"写库完成，实际更新行数: {updated}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
