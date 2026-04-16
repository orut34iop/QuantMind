import argparse
import datetime as dt
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

import numpy as np
from tqdm import tqdm

try:
    import baostock as bs
except Exception as exc:
    raise SystemExit(
        "Missing dependency: baostock. Install in project .venv first."
    ) from exc


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
    if not value or str(value).strip() == "":
        return np.nan
    try:
        return float(value)
    except ValueError:
        return np.nan


def load_calendar(cal_path: Path) -> List[str]:
    if not cal_path.exists():
        return []
    return [x.strip() for x in cal_path.read_text(encoding="utf-8").splitlines() if x.strip()]


def fetch_trade_dates(start_date: str, end_date: str) -> List[str]:
    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    out = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        if row[1] == "1":
            out.append(row[0])
    return out


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
            date=row[0],
            open=parse_float(row[1]),
            high=parse_float(row[2]),
            low=parse_float(row[3]),
            close=parse_float(row[4]),
            preclose=parse_float(row[5]),
            volume=parse_float(row[6]),
            amount=parse_float(row[7]),
            pct_chg=parse_float(row[8]),
        )
        out[k.date] = k
    return out


def filter_available_dates(dates: List[str]) -> List[str]:
    if not dates: return []
    # 使用 SH600000 作为 A 股全市场数据同步的“水位线”
    # 只有基准股票有对应的日线数据，才认为该交易日已结算可同步
    rs = bs.query_history_k_data_plus("sh.600000", "date", 
                                      start_date=dates[0], end_date=dates[-1], 
                                      frequency="d")
    available = set()
    while rs.error_code == "0" and rs.next():
        available.add(rs.get_row_data()[0])
    return [d for d in dates if d in available]


def load_sh_sz_instruments(all_txt: Path) -> List[str]:
    if not all_txt.exists(): return []
    instruments = []
    for line in all_txt.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        code = line.split()[0].upper()
        if code.startswith(("SH", "SZ")):
            instruments.append(code)
    return sorted(set(instruments))


def to_baostock_code(inst: str) -> str:
    if inst.startswith("SH"): return f"sh.{inst[2:]}"
    if inst.startswith("SZ"): return f"sz.{inst[2:]}"
    return inst.lower()


def build_feature_values(row: Optional[KRow], factor: float, bin_name: str) -> float:
    # 缺失值策略：价格类使用 NaN，成交量比例类使用 0.0
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
        # 成交量单位通常为手，Qlib 紧凑格式中 volume 会除以 factor 还原
        return row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
    if bin_name == "amount": 
        return row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
    if bin_name == "change":
        if np.isfinite(row.pct_chg): return row.pct_chg / 100.0
        if np.isfinite(row.preclose) and row.preclose != 0: return (row.close - row.preclose) / row.preclose
        return np.nan
    if bin_name == "vwap":
        v = row.volume / (100.0 * factor) if (np.isfinite(row.volume) and factor > 0) else 0.0
        a = row.amount / 1000.0 if np.isfinite(row.amount) else 0.0
        return (a / v * 10.0) if (v > 0 and np.isfinite(a)) else np.nan
    
    return np.nan


def process_bin_file(bin_path: Path, existing_calendar: List[str], missing_dates: List[str], 
                     new_data_map: Dict[str, KRow], factor: float, apply: bool):
    bin_name = bin_path.name.split(".")[0]
    
    if not bin_path.exists():
        return # Skip missing bins

    # Read existing data
    with open(bin_path, "rb") as f:
        data = f.read()
    
    arr = np.frombuffer(data, dtype="<f4").copy()
    
    # 核心对齐逻辑
    # 我们根据日期来识别每个记录应该在的位置
    full_dates = sorted(list(set(existing_calendar + missing_dates)))
    new_arr = np.full(len(full_dates), np.nan, dtype="<f4")
    if bin_name.lower() in ("volume", "amount"):
        new_arr[:] = 0.0
        
    # 填充旧数据
    date_to_idx = {d: i for i, d in enumerate(full_dates)}
    for i, d in enumerate(existing_calendar):
        if i < len(arr):
            idx = date_to_idx.get(d)
            if idx is not None:
                new_arr[idx] = arr[i]

    # 填充新/缺失数据
    for d in missing_dates:
        row = new_data_map.get(d)
        new_arr[date_to_idx[d]] = build_feature_values(row, factor, bin_name)

    if apply:
        with open(bin_path, "wb") as f:
            f.write(new_arr.tobytes())


def main():
    parser = argparse.ArgumentParser(description="Qlib 增量全量补齐工具 (Baostock)")
    parser.add_argument("--qlib-dir", default="db/qlib_data", help="Qlib 数据根目录")
    parser.add_argument("--end-date", help="同步结束日期")
    parser.add_argument("--apply", action="store_true", help="执行写入")
    args = parser.parse_args()

    qlib_dir = Path(args.qlib_dir).resolve()
    cal_path = qlib_dir / "calendars" / "day.txt"
    features_root = qlib_dir / "features"
    all_txt = qlib_dir / "instruments" / "all.txt"

    bs.login()
    try:
        existing_calendar = load_calendar(cal_path)
        if not existing_calendar:
            print("Error: Calendar is empty.")
            return

        start_date = existing_calendar[0]
        end_date = args.end_date or dt.date.today().isoformat()
        
        print(f"Checking calendar from {start_date} to {end_date}...")
        ideal_calendar = fetch_trade_dates(start_date, end_date)
        
        # 过滤出真正有数据的日期
        ideal_calendar = filter_available_dates(ideal_calendar)
        
        missing_dates = sorted([d for d in ideal_calendar if d not in existing_calendar])
        if not missing_dates:
            print("No missing dates found. Everything is up to date.")
            return
            
        print(f"Found {len(missing_dates)} missing dates (Gap/Tail).")
        
        sh_sz = load_sh_sz_instruments(all_txt)
        print(f"Processing {len(sh_sz)} instruments...")

        # Batch fetch benchmark to check data availability
        # We assume if SH600000 has data, the market is open.
        # But for efficiency, we will fetch per-instrument.
        
        # 为了提高效率，我们将按日期对缺失数据进行分批抓取
        # 这里为了简单，我们还是遍历股票
        
        for inst in tqdm(sh_sz):
            inst_dir = features_root / inst.lower()
            if not inst_dir.exists(): continue
            
            factor_bin = inst_dir / "factor.day.bin"
            if not factor_bin.exists(): continue
            
            # Read last factor
            with open(factor_bin, "rb") as f:
                f.seek(-4, os.SEEK_END)
                last_factor = struct.unpack("<f", f.read(4))[0]

            # Fetch missing rows for this instrument
            new_data = fetch_krows(to_baostock_code(inst), missing_dates[0], missing_dates[-1])
            
            for bin_name in REQUIRED_BINS:
                bin_path = inst_dir / f"{bin_name}.day.bin"
                process_bin_file(bin_path, existing_calendar, missing_dates, new_data, last_factor, args.apply)

        if args.apply:
            # Update day.txt
            final_calendar = sorted(list(set(existing_calendar + missing_dates)))
            os.rename(cal_path, str(cal_path) + ".bak")
            with open(cal_path, "w") as f:
                for d in final_calendar:
                    f.write(f"{d}\n")
            
            # Update instruments/*.txt (simplified end date sync)
            for txt_file in (qlib_dir / "instruments").glob("*.txt"):
                content = txt_file.read_text()
                # Dummy update end date approach
                lines = content.splitlines()
                new_lines = []
                for l in lines:
                    parts = l.split()
                    if len(parts) >= 3 and parts[0].upper().startswith(("SH", "SZ")):
                        parts[2] = final_calendar[-1]
                        new_lines.append("\t".join(parts))
                    else:
                        new_lines.append(l)
                txt_file.write_text("\n".join(new_lines) + "\n")

            print("Done! Calendar and all binary files updated.")
        else:
            print("Dry-run finished. Use --apply to commit changes.")

    finally:
        bs.logout()

if __name__ == "__main__":
    main()

