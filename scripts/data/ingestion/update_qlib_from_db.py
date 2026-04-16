#!/usr/bin/env python3
"""
从 PostgreSQL market_data_daily 表读取数据，并补齐 Qlib 二进制数据 (db/qlib_data)。
取代直接从 Baostock 拉取，减轻外部 API 压力并确保数据一致性。
"""

import argparse
import datetime as dt
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sqlalchemy import create_engine, text
from tqdm import tqdm

REQUIRED_BINS = (
    "open", "high", "low", "close", "vwap", 
    "volume", "amount", "factor", "adjclose", "change"
)

@dataclass
class KRow:
    date: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    preclose: float
    volume: float
    amount: float
    pct_chg: float


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
        if not all([host, port, user, password, db]):
            raise RuntimeError("Missing DB env vars for sync")
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return _to_sync_db_url(db_url)


def load_calendar(cal_path: Path) -> List[str]:
    if not cal_path.exists():
        return []
    return [x.strip() for x in cal_path.read_text(encoding="utf-8").splitlines() if x.strip()]


def fetch_db_trade_dates(engine, start_date: str, end_date: str) -> List[str]:
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT DISTINCT date FROM market_data_daily WHERE date >= :s AND date <= :e ORDER BY date"),
            {"s": start_date, "e": end_date}
        ).fetchall()
        return [str(r[0]) for r in res]


def fetch_db_krows(engine, symbols: List[str], dates: List[str]) -> Dict[str, Dict[str, KRow]]:
    """返回 symbol -> date -> KRow"""
    if not symbols or not dates:
        return {}
    
    out = {s: {} for s in symbols}
    row_count = 0
    with engine.connect() as conn:
        # 分批查询 symbols 避免 SQL 过长
        batch_size = 500
        for i in range(0, len(symbols), batch_size):
            # 关键点：DB 存的是小写
            chunk = [s.lower() for s in symbols[i : i + batch_size]]
            res = conn.execute(
                text("""
                    SELECT date, symbol, open, high, low, close, volume, amount
                    FROM market_data_daily 
                    WHERE symbol IN :symbols AND date IN :dates
                """),
                {"symbols": tuple(chunk), "dates": tuple(dates)}
            ).fetchall()

            for r in res:
                row_count += 1
                d_str = str(r[0])
                s_db = r[1]
                s_orig = s_db.upper() # 映射回大写以匹配 Qlib

                close_v = float(r[5]) if r[5] is not None else np.nan

                pre_v = close_v
                
                k = KRow(
                    date=d_str,
                    symbol=s_orig,
                    open=float(r[2]) if r[2] is not None else np.nan,
                    high=float(r[3]) if r[3] is not None else np.nan,
                    low=float(r[4]) if r[4] is not None else np.nan,
                    close=close_v,
                    preclose=pre_v,
                    volume=float(r[6]) if r[6] is not None else 0.0,
                    amount=float(r[7]) if r[7] is not None else 0.0,
                    pct_chg=0.0
                )
                if s_orig in out:
                    out[s_orig][d_str] = k
    print(f"  [DB] Fetched {row_count} rows from database.", file=sys.stdout, flush=True)
    return out


def build_feature_values(row: Optional[KRow], factor: float, bin_name: str) -> float:
    is_volume_type = bin_name.lower() in ("volume", "amount")
    default_empty = 0.0 if is_volume_type else np.nan
    
    if row is None:
        return default_empty

    if bin_name == "open": return row.open * factor if np.isfinite(row.open) else np.nan
    if bin_name == "high": return row.high * factor if np.isfinite(row.high) else np.nan
    if bin_name == "low": return row.low * factor if np.isfinite(row.low) else np.nan
    if bin_name == "close": return row.close * factor if np.isfinite(row.close) else np.nan
    if bin_name == "adjclose": return row.close if np.isfinite(row.close) else np.nan
    if bin_name == "factor": return factor
    if bin_name == "volume": 
        return row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
    if bin_name == "amount": 
        return row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
    if bin_name == "change":
        return row.pct_chg / 100.0 if np.isfinite(row.pct_chg) else np.nan
    if bin_name == "vwap":
        v = row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
        a = row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
        return (a / v * 10.0) if (v > 0 and np.isfinite(a)) else np.nan
    
    return np.nan


def process_bin_file(bin_path: Path, existing_calendar: List[str], missing_dates: List[str], 
                      new_data_map: Dict[str, KRow], factor: float, apply: bool):
    bin_name = bin_path.name.split(".")[0]
    if not bin_path.exists():
        return

    with open(bin_path, "rb") as f:
        data = f.read()
    
    # 原始数组 [start_index, data...]
    raw_arr = np.frombuffer(data, dtype="<f4").copy()
    if len(raw_arr) < 1:
        return
        
    start_idx = int(raw_arr[0])
    arr = raw_arr[1:]
    
    # 构建新数组，长度对齐到全量日历
    full_dates = sorted(list(set(existing_calendar + missing_dates)))
    new_data_len = len(full_dates) - start_idx
    if new_data_len <= 0:
        return # 异常情况
        
    new_vals = np.full(new_data_len, np.nan, dtype="<f4")
    if bin_name.lower() in ("volume", "amount"):
        new_vals[:] = 0.0
        
    # 1. 迁移旧数据
    # arr 对应的是 existing_calendar[start_idx : start_idx + len(arr)]
    for i in range(len(arr)):
        if start_idx + i < len(full_dates):
            new_vals[i] = arr[i]
            
    # 2. 回填或追加新数据
    # 遍历全量日历中对应的位置
    for i in range(new_data_len):
        cal_idx = start_idx + i
        if cal_idx >= len(full_dates):
            break
            
        d = full_dates[cal_idx]
        # 如果当前位置是 NaN，或者是新日期，则尝试从 new_data_map 获取
        is_empty = np.isnan(new_vals[i]) or (bin_name.lower() in ("volume", "amount") and new_vals[i] == 0)
        
        if (is_empty or d in missing_dates) and d in new_data_map:
            row = new_data_map.get(d)
            new_val = build_feature_values(row, factor, bin_name)
            if not np.isnan(new_val):
                new_vals[i] = new_val

    if apply:
        # 重新组合：[start_index, new_vals...]
        fixed_data = np.concatenate(([np.float32(start_idx)], new_vals)).astype("<f4")
        with open(bin_path, "wb") as f:
            f.write(fixed_data.tobytes())


def main():
    parser = argparse.ArgumentParser(description="从数据库同步数据到 Qlib 二进制文件")
    parser.add_argument("--qlib-dir", default="db/qlib_data", help="Qlib 数据根目录")
    parser.add_argument("--apply", action="store_true", help="执行写入")
    args = parser.parse_args()

    qlib_dir = Path(args.qlib_dir).resolve()
    cal_path = qlib_dir / "calendars" / "day.txt"
    features_root = qlib_dir / "features"
    all_txt = qlib_dir / "instruments" / "all.txt"

    engine = create_engine(_resolve_db_url())
    
    existing_calendar = load_calendar(cal_path)
    if not existing_calendar:
        print("Error: Calendar is empty.")
        return

    # 仅查询最近 10 天的数据进行补齐，避免全量查询导致超时或性能问题
    last_cal_date = existing_calendar[-1]
    start_date = (dt.date.fromisoformat(last_cal_date) - dt.timedelta(days=10)).isoformat()
    end_date = dt.date.today().isoformat()
    
    print(f"Checking DB calendar from {start_date} to {end_date}...", file=sys.stdout, flush=True)
    db_trade_dates = fetch_db_trade_dates(engine, start_date, end_date)
    
    missing_dates = sorted([d for d in db_trade_dates if d not in existing_calendar])
    if missing_dates:
        print(f"Found {len(missing_dates)} missing dates in Qlib: {missing_dates}", file=sys.stdout, flush=True)
    else:
        print("No new dates to append, checking for existing NaN gaps to backfill...", file=sys.stdout, flush=True)
    
    # 强制将需要补齐的日期也加入查询范围（即使已在日历中）
    check_backfill_dates = sorted(list(set(db_trade_dates))) 

    # 加载所有标的
    symbols = []
    if all_txt.exists():
        for line in all_txt.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            code = line.split()[0].upper()
            # 兼容指数和股票
            if code.startswith(("SH", "SZ")):
                symbols.append(code)
    
    print(f"Fetching data and updating binary files in batches (total {len(symbols)} symbols)...", file=sys.stdout, flush=True)
    batch_size = 1000
    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i : i + batch_size]
        print(f"Processing batch {i//batch_size + 1}: {len(batch_symbols)} symbols...", file=sys.stdout, flush=True)
        
        db_data = fetch_db_krows(engine, batch_symbols, check_backfill_dates)
        
        for inst in tqdm(batch_symbols, file=sys.stdout):
            inst_dir = features_root / inst.lower()
            if not inst_dir.exists(): continue
            
            factor_bin = inst_dir / "factor.day.bin"
            if not factor_bin.exists(): 
                last_factor = 1.0
            else:
                with open(factor_bin, "rb") as f:
                    f.seek(-4, os.SEEK_END)
                    last_factor = struct.unpack("<f", f.read(4))[0]

            inst_data = db_data.get(inst, {})
            for bin_name in REQUIRED_BINS:
                bin_path = inst_dir / f"{bin_name}.day.bin"
                process_bin_file(bin_path, existing_calendar, missing_dates, inst_data, last_factor, args.apply)

    if args.apply:
        # Update day.txt
        final_calendar = sorted(list(set(existing_calendar + missing_dates)))
        with open(cal_path, "w") as f:
            for d in final_calendar:
                f.write(f"{d}\n")
        
        # Update instruments (end date)
        for txt_file in (qlib_dir / "instruments").glob("*.txt"):
            lines = txt_file.read_text().splitlines()
            new_lines = []
            for l in lines:
                parts = l.split()
                if len(parts) >= 3 and parts[0].upper().startswith(("SH", "SZ")):
                    parts[2] = final_calendar[-1]
                    new_lines.append("\t".join(parts))
                else:
                    new_lines.append(l)
            txt_file.write_text("\n".join(new_lines) + "\n")

        print("Done! Qlib binary data synchronized from DB.", file=sys.stdout, flush=True)
    else:
        print("Dry-run finished. Use --apply to commit changes.", file=sys.stdout, flush=True)


if __name__ == "__main__":
    main()
