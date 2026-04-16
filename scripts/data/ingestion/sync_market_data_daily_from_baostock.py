#!/usr/bin/env python3
"""
从 Baostock 拉取日线并补齐 market_data_daily。

写入策略（自动适配表结构）：
1. 若存在基础行情列（open/high/low/close...），写基础字段模式。
2. 否则若存在 feature_0..N 列，写 feature 向量模式（并可选同步 features JSON）。

默认 dry-run，添加 --apply 才会写库。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import create_engine, text

try:
    import baostock as bs
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: baostock. Install in project .venv first, e.g. `pip install baostock`."
    ) from exc


def _to_sync_db_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return raw


def _resolve_db_url() -> str:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
        port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        db = os.getenv("DB_NAME")
        missing = [
            k
            for k, v in (
                ("DB_HOST", host),
                ("DB_PORT", port),
                ("DB_USER", user),
                ("DB_PASSWORD", password),
                ("DB_NAME", db),
            )
            if not v
        ]
        if missing:
            raise RuntimeError(f"Missing DB env vars: {', '.join(missing)}")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return _to_sync_db_url(db_url)


def _parse_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if math.isfinite(f):
        return f
    return None


def _normalize_symbol(bs_code: str) -> Optional[str]:
    c = (bs_code or "").strip().lower()
    if c.startswith("sh."):
        return f"sh{c[3:]}"
    if c.startswith("sz."):
        return f"sz{c[3:]}"
    return None


def _is_sh_sz(bs_code: str) -> bool:
    c = (bs_code or "").strip().lower()
    return c.startswith("sh.") or c.startswith("sz.")


def _query_trade_days(start_date: str, end_date: str) -> List[str]:
    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    if rs.error_code != "0":
        raise RuntimeError(f"query_trade_dates failed: {rs.error_code} {rs.error_msg}")
    out: List[str] = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if len(row) >= 2 and row[1] == "1":
            out.append(row[0])
    return out


def _has_benchmark_data(trade_date: str) -> bool:
    rs = bs.query_history_k_data_plus(
        "sh.600000",
        "date,close",
        start_date=trade_date,
        end_date=trade_date,
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != "0":
        return False
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if row and row[0] == trade_date:
            return True
    return False


def _resolve_effective_trade_date(target_date: str) -> str:
    d = dt.date.fromisoformat(target_date)
    start = (d - dt.timedelta(days=14)).isoformat()
    days = _query_trade_days(start_date=start, end_date=target_date)
    days = [x for x in days if x <= target_date]
    for day in reversed(days):
        if _has_benchmark_data(day):
            return day
    raise RuntimeError(f"No effective trading day with data found up to {target_date}")


def _query_symbols(trade_date: str) -> List[str]:
    rs = bs.query_all_stock(day=trade_date)
    if rs.error_code != "0":
        raise RuntimeError(f"query_all_stock failed: {rs.error_code} {rs.error_msg}")
    out: List[str] = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if not row:
            continue
        code = row[0]
        if _is_sh_sz(code):
            out.append(code)
    return sorted(set(out))


def _fetch_table_columns(conn) -> Set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'market_data_daily'
            """
        )
    ).fetchall()
    return {str(r[0]) for r in rows}


def _feature_columns(columns: Set[str]) -> List[str]:
    out: List[Tuple[int, str]] = []
    for c in columns:
        if c.startswith("feature_"):
            suffix = c.split("_", 1)[1]
            if suffix.isdigit():
                out.append((int(suffix), c))
    out.sort(key=lambda x: x[0])
    return [c for _, c in out]


    adj_factor: float
    turn: float

DELETE_OLD_SQL = text(
    """
    DELETE FROM market_data_daily
    WHERE date < :target_date
    """
)


def _build_basic_upsert_sql(columns: Set[str]) -> Tuple[Any, List[str], str]:
    candidates = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "vwap",
        "returns_1d",
        "turnover_rate",
        "pe_ttm",
        "pb",
        "ps_ttm",
        "pcf_ncf_ttm",
        "is_st",
        "adj_factor",
    ]
    selected = [c for c in candidates if c in columns]
    if not selected:
        raise RuntimeError("market_data_daily 不包含可写入的基础行情列")

    insert_cols = ["date", "symbol"] + selected
    placeholders = ", ".join(f":{c}" for c in insert_cols)
    update_cols = ",\n        ".join(f"{c} = EXCLUDED.{c}" for c in selected)
    if "updated_at" in columns:
        update_cols += ",\n        updated_at = NOW()"

    sql = text(
        f"""
        INSERT INTO market_data_daily ({", ".join(insert_cols)})
        VALUES ({placeholders})
        ON CONFLICT (date, symbol) DO UPDATE SET
        {update_cols}
        """
    )
    return sql, selected, "basic_fields"


def _build_feature_upsert_sql(columns: Set[str], feature_cols: Sequence[str]) -> Tuple[Any, List[str], str]:
    insert_cols = ["date", "symbol"] + list(feature_cols)
    if "features" in columns:
        insert_cols.append("features")

    value_exprs: List[str] = []
    for c in insert_cols:
        if c == "features":
            value_exprs.append("CAST(:features AS jsonb)")
        else:
            value_exprs.append(f":{c}")
    placeholders = ", ".join(value_exprs)
    update_cols = ",\n        ".join(f"{c} = EXCLUDED.{c}" for c in insert_cols if c not in {"date", "symbol"})
    if "updated_at" in columns:
        update_cols += ",\n        updated_at = NOW()"

    sql = text(
        f"""
        INSERT INTO market_data_daily ({", ".join(insert_cols)})
        VALUES ({placeholders})
        ON CONFLICT (date, symbol) DO UPDATE SET
        {update_cols}
        """
    )
    return sql, list(feature_cols), "feature_columns"


def _record_to_feature_values(record: Dict[str, Any], feature_len: int) -> List[float]:
    vec = [0.0] * feature_len

    mapping = {
        0: record.get("open"),
        1: record.get("high"),
        2: record.get("low"),
        3: record.get("close"),
        4: record.get("volume"),
        5: record.get("amount"),
        6: record.get("vwap"),
        7: record.get("returns_1d"),
        8: record.get("turnover_rate"),
        9: record.get("adj_factor"),
        10: record.get("preclose"),
    }
    for idx, val in mapping.items():
        if idx < feature_len:
            vec[idx] = float(val) if val is not None else 0.0
    return vec


@dataclass
class SyncStats:
    mode: str
    requested_date: str
    effective_trade_date: str
    write_mode: str = ""
    symbols_total: int = 0
    symbols_ok: int = 0
    symbols_failed: int = 0
    rows_upserted: int = 0
    error_samples: List[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "requested_date": self.requested_date,
            "effective_trade_date": self.effective_trade_date,
            "write_mode": self.write_mode,
            "symbols_total": self.symbols_total,
            "symbols_ok": self.symbols_ok,
            "symbols_failed": self.symbols_failed,
            "rows_upserted": self.rows_upserted,
            "error_samples": self.error_samples or [],
        }


def _fetch_one_day_row(bs_code: str, trade_date: str) -> Optional[Dict[str, Any]]:
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,code,open,high,low,close,preclose,volume,amount,pctChg,turn,psTTM,pcfNcfTTM,isST",
        start_date=trade_date,
        end_date=trade_date,
        frequency="d",
        adjustflag="3",
    )
    if rs.error_code != "0":
        raise RuntimeError(f"{bs_code} query failed: {rs.error_code} {rs.error_msg}")
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if len(row) < 11:
            continue
        symbol = _normalize_symbol(row[1])
        if not symbol:
            return None
        open_p = _parse_float(row[2])
        high_p = _parse_float(row[3])
        low_p = _parse_float(row[4])
        close_p = _parse_float(row[5])
        preclose = _parse_float(row[6])
        volume = _parse_float(row[7])
        amount = _parse_float(row[8])
        pct_chg = _parse_float(row[9])
        turn = _parse_float(row[10])
        ps_ttm = _parse_float(row[11])
        pcf_ncf_ttm = _parse_float(row[12])
        is_st = 1 if str(row[13]) == "1" else 0

        vwap = None
        if amount is not None and volume is not None and volume > 0:
            vwap = amount / volume

        returns_1d = None
        if pct_chg is not None:
            returns_1d = pct_chg / 100.0
        elif close_p is not None and preclose is not None and preclose != 0:
            returns_1d = (close_p / preclose) - 1.0

        turnover_rate = (turn / 100.0) if turn is not None else None

        return {
            "date": dt.date.fromisoformat(trade_date),
            "symbol": symbol,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "preclose": preclose,
            "volume": volume,
            "amount": amount,
            "vwap": vwap,
            "returns_1d": returns_1d,
            "turnover_rate": turnover_rate,
            "ps_ttm": ps_ttm,
            "pcf_ncf_ttm": pcf_ncf_ttm,
            "is_st": is_st,
            "adj_factor": 1.0,
        }
    return None


def _build_write_payloads(records: Sequence[Dict[str, Any]], columns: Set[str]) -> Tuple[Any, List[Dict[str, Any]], str]:
    required_key_cols = {"date", "symbol"}
    if not required_key_cols.issubset(columns):
        raise RuntimeError("market_data_daily 缺少主键列 date/symbol")

    if {"open", "high", "low", "close"}.issubset(columns):
        upsert_sql, write_cols, write_mode = _build_basic_upsert_sql(columns)
        payloads: List[Dict[str, Any]] = []
        for r in records:
            p = {"date": r["date"], "symbol": r["symbol"]}
            for c in write_cols:
                p[c] = r.get(c)
            payloads.append(p)
        return upsert_sql, payloads, write_mode

    feature_cols = _feature_columns(columns)
    if feature_cols:
        upsert_sql, _, write_mode = _build_feature_upsert_sql(columns, feature_cols)
        feature_len = len(feature_cols)
        payloads = []
        for r in records:
            vec = _record_to_feature_values(r, feature_len)
            p: Dict[str, Any] = {"date": r["date"], "symbol": r["symbol"]}
            for i, col in enumerate(feature_cols):
                p[col] = vec[i]
            if "features" in columns:
                p["features"] = json.dumps(vec, ensure_ascii=False)
            payloads.append(p)
        return upsert_sql, payloads, write_mode

    raise RuntimeError("market_data_daily 既不包含基础行情列，也不包含 feature_0..N 列，无法写入")


def main() -> int:
    parser = argparse.ArgumentParser(description="Baostock -> market_data_daily 同步")
    parser.add_argument("--target-date", help="目标日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--max-symbols", type=int, default=0, help="仅处理前 N 个标的（0=全部）")
    parser.add_argument("--apply", action="store_true", help="执行写入（默认 dry-run）")
    args = parser.parse_args()

    requested_date = args.target_date or dt.date.today().isoformat()
    stats = SyncStats(
        mode="APPLY" if args.apply else "DRY-RUN",
        requested_date=requested_date,
        effective_trade_date="",
        error_samples=[],
    )

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_code} {login.error_msg}")

    try:
        effective_trade_date = _resolve_effective_trade_date(requested_date)
        stats.effective_trade_date = effective_trade_date
        symbols = _query_symbols(effective_trade_date)
        if args.max_symbols and args.max_symbols > 0:
            symbols = symbols[: args.max_symbols]
        stats.symbols_total = len(symbols)

        print(
            f"[PLAN] mode={stats.mode} requested_date={requested_date} "
            f"effective_trade_date={effective_trade_date} symbols={len(symbols)}"
        )

        records: List[Dict[str, Any]] = []
        for idx, bs_code in enumerate(symbols, start=1):
            try:
                row = _fetch_one_day_row(bs_code, effective_trade_date)
                if row is None:
                    stats.symbols_failed += 1
                    if len(stats.error_samples or []) < 20:
                        stats.error_samples.append({"symbol": bs_code, "error": "no_daily_row"})
                    continue
                records.append(row)
                stats.symbols_ok += 1
            except Exception as e:  # pragma: no cover
                stats.symbols_failed += 1
                if len(stats.error_samples or []) < 20:
                    stats.error_samples.append({"symbol": bs_code, "error": str(e)[:200]})

            if idx % 300 == 0 or idx == len(symbols):
                progress_msg = f"[PROGRESS] {idx}/{len(symbols)} ok={stats.symbols_ok} failed={stats.symbols_failed}"
                print(progress_msg, file=sys.stdout, flush=True)

        if records:
            engine = create_engine(_resolve_db_url(), pool_pre_ping=True)
            with engine.connect() as conn:
                columns = _fetch_table_columns(conn)
            upsert_sql, payloads, write_mode = _build_write_payloads(records, columns)
            stats.write_mode = write_mode
        else:
            upsert_sql, payloads = None, []
            stats.write_mode = "no_records"

        if args.apply and payloads:
            engine = create_engine(_resolve_db_url(), pool_pre_ping=True)
            batch_size = 1000
            with engine.begin() as conn:
                # 1-day retention: delete older data first
                print(f"[RETAIN] Cleaning data older than {effective_trade_date}...")
                conn.execute(DELETE_OLD_SQL, {"target_date": effective_trade_date})
                
                for i in range(0, len(payloads), batch_size):
                    chunk = payloads[i : i + batch_size]
                    conn.execute(upsert_sql, chunk)
                    stats.rows_upserted += len(chunk)
        else:
            stats.rows_upserted = len(payloads)

        print(
            f"[DONE] mode={stats.mode} effective_trade_date={stats.effective_trade_date} "
            f"write_mode={stats.write_mode} symbols_ok={stats.symbols_ok} "
            f"symbols_failed={stats.symbols_failed} rows_upserted={stats.rows_upserted}"
        )
        print(json.dumps({"success": True, **stats.to_dict()}, ensure_ascii=False))
        return 0
    finally:
        bs.logout()


if __name__ == "__main__":
    raise SystemExit(main())
