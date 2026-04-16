import argparse
import datetime as dt
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from tqdm import tqdm

try:
    import baostock as bs
except Exception as exc:
    raise SystemExit("Missing dependency: baostock. Install in project .venv first.")

REQUIRED_BINS = (
    "open", "high", "low", "close", "vwap", 
    "volume", "amount", "factor", "adjclose", "change"
)

@dataclass
class KRow:
    date: str
    open: float
    high: float
    low: float
    close: float
    preclose: float
    volume: float
    amount: float
    pct_chg: float

def parse_float(value: str) -> float:
    if not value or str(value).strip() == "": return np.nan
    try: return float(value)
    except ValueError: return np.nan

def fetch_krows(code: str, start_date: str, end_date: str) -> Dict[str, KRow]:
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,preclose,volume,amount,pctChg",
        start_date=start_date, end_date=end_date,
        frequency="d", adjustflag="3"
    )
    out = {}
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        k = KRow(
            date=row[0], open=parse_float(row[1]),
            high=parse_float(row[2]), low=parse_float(row[3]),
            close=parse_float(row[4]), preclose=parse_float(row[5]),
            volume=parse_float(row[6]), amount=parse_float(row[7]),
            pct_chg=parse_float(row[8]),
        )
        out[k.date] = k
    return out

def build_feature_value(row: Optional[KRow], factor: float, bin_name: str) -> float:
    is_volume_type = bin_name.lower() in ("volume", "amount")
    default_empty = 0.0 if is_volume_type else np.nan
    if row is None: return default_empty

    if bin_name == "open": return row.open * factor if np.isfinite(row.open) else np.nan
    if bin_name == "high": return row.high * factor if np.isfinite(row.high) else np.nan
    if bin_name == "low": return row.low * factor if np.isfinite(row.low) else np.nan
    if bin_name == "close": return row.close * factor if np.isfinite(row.close) else np.nan
    if bin_name == "adjclose": return row.close if np.isfinite(row.close) else np.nan
    if bin_name == "factor": return factor
    if bin_name == "volume": return row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
    if bin_name == "amount": return row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
    if bin_name == "change":
        if np.isfinite(row.pct_chg): return row.pct_chg / 100.0
        if np.isfinite(row.preclose) and row.preclose != 0: return (row.close - row.preclose) / row.preclose
        return np.nan
    if bin_name == "vwap":
        v = row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
        a = row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
        return (a / v * 10.0) if (v > 0 and np.isfinite(a)) else np.nan
    return np.nan

def main():
    parser = argparse.ArgumentParser(description="Qlib 数据断档专门补全工具 (Baostock)")
    parser.add_argument("--qlib-dir", default="db/qlib_data", help="Qlib 数据根目录")
    parser.add_argument("--start-date", default="2026-01-01", help="补全起始日期")
    parser.add_argument("--end-date", default="2026-03-18", help="补全结束日期")
    parser.add_argument("--max-symbols", type=int, default=0, help="处理前 N 只股票 (0=全部)")
    parser.add_argument("--apply", action="store_true", help="执行写入")
    args = parser.parse_args()

    qlib_dir = Path(args.qlib_dir).resolve()
    cal_path = qlib_dir / "calendars" / "day.txt"
    features_root = qlib_dir / "features"
    all_txt = qlib_dir / "instruments" / "all.txt"

    # 1. 识别日期索引
    calendar = [x.strip() for x in cal_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    date_to_idx = {d: i for i, d in enumerate(calendar)}
    
    target_dates = [d for d in calendar if args.start_date <= d <= args.end_date]
    if not target_dates:
        print(f"Error: No dates found in calendar for range {args.start_date} to {args.end_date}")
        return

    print(f"Targeting {len(target_dates)} dates, index range: {date_to_idx[target_dates[0]]} to {date_to_idx[target_dates[-1]]}")

    # 2. 读取股票列表
    sh_sz = []
    if all_txt.exists():
        for line in all_txt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                code = line.split()[0].upper()
                if code.startswith(("SH", "SZ")): sh_sz.append(code)
    
    if args.max_symbols > 0: sh_sz = sh_sz[:args.max_symbols]
    print(f"Processing {len(sh_sz)} instruments...")

    bs.login()
    try:
        for inst in tqdm(sh_sz):
            inst_dir = features_root / inst.lower()
            if not inst_dir.exists(): continue
            
            # 读取因子
            factor_bin = inst_dir / "factor.day.bin"
            if not factor_bin.exists(): continue
            # 从最后一天读 factor (假设 factor 不变)
            with open(factor_bin, "rb") as f:
                f.seek(-4, os.SEEK_END)
                factor = struct.unpack("<f", f.read(4))[0]
            
            # 抓取数据
            bs_code = f"sh.{inst[2:]}" if inst.startswith("SH") else f"sz.{inst[2:]}"
            rows = fetch_krows(bs_code, target_dates[0], target_dates[-1])

            # 在线修改 (In-place)
            for bin_name in REQUIRED_BINS:
                bin_path = inst_dir / f"{bin_name}.day.bin"
                if not bin_path.exists(): continue
                
                # 读取该文件的 start_index (Header)
                with open(bin_path, "rb") as f:
                    file_start_idx = struct.unpack("<I", f.read(4))[0]
                
                # 计算更新的数据块
                new_vals = []
                for d in target_dates:
                    new_vals.append(build_feature_value(rows.get(d), factor, bin_name))
                
                # 计算在 binary 文件中的相对索引和偏量
                # row 0 (offset 4) corresponds to file_start_idx
                rel_idx = date_to_idx[target_dates[0]] - file_start_idx
                if rel_idx < 0:
                    # 如果补全起始日期早于文件起始日期，跳过该标的或截断处理
                    # 这里选择跳过，以免 offset 溢出，建议手动处理此类标的
                    continue

                offset = 4 + (rel_idx * 4)
                
                if args.apply:
                    with open(bin_path, "r+b") as f:
                        f.seek(offset)
                        f.write(np.asarray(new_vals, dtype=np.float32).tobytes())
                        
                    # 额外对齐：如果文件长度超过了当前日历允许的长度，执行截断
                    max_rows = len(calendar) - file_start_idx
                    expected_size = 4 + max_rows * 4
                    if bin_path.stat().st_size > expected_size:
                        with open(bin_path, "r+b") as f:
                            f.truncate(expected_size)
        
        if not args.apply:
            print("Dry-run finished. Use --apply to commit changes.")
        else:
            print("Done! Gap successfully backfilled.")

    finally:
        bs.logout()

if __name__ == "__main__":
    main()
