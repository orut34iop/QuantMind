import os
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
import struct

# 配置
QLIB_DIR = Path("/app/db/qlib_data")
DB_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "+psycopg2")

def fix_index_data():
    engine = create_engine(DB_URL)
    cal_path = QLIB_DIR / "calendars" / "day.txt"
    calendar = open(cal_path).read().splitlines()
    target_date = "2026-03-25"
    
    if target_date not in calendar:
        print(f"Date {target_date} not in calendar")
        return
        
    date_idx = calendar.index(target_date)
    
    indices = ["sh000300", "sh000001", "sz399001"]
    
    with engine.connect() as conn:
        for idx_code in indices:
            print(f"Fixing {idx_code}...")
            row = conn.execute(
                text("SELECT open, high, low, close, volume, amount FROM market_data_daily WHERE symbol=:s AND date=:d"),
                {"s": idx_code, "d": target_date}
            ).first()
            
            if not row:
                print(f"  No data in DB for {idx_code}")
                continue
                
            data_map = {
                "open": float(row[0]),
                "high": float(row[1]),
                "low": float(row[2]),
                "close": float(row[3]),
                "volume": float(row[4]),
                "amount": float(row[5])
            }
            
            feat_dir = QLIB_DIR / "features" / idx_code.lower()
            if not feat_dir.exists():
                print(f"  Directory {feat_dir} does not exist")
                continue
                
            for field, val in data_map.items():
                bin_path = feat_dir / f"{field}.day.bin"
                if not bin_path.exists(): continue
                
                with open(bin_path, "rb") as f:
                    raw = np.frombuffer(f.read(), dtype="<f4").copy()
                
                start_idx = int(raw[0])
                # 数据部分在 raw[1:]
                # 目标日期在全量日历中的索引是 date_idx
                # 在 raw[1:] 数组中的对应位置是 date_idx - start_idx
                arr_pos = date_idx - start_idx + 1
                
                if arr_pos < len(raw):
                    print(f"  Updating {field} at pos {arr_pos} with value {val}")
                    raw[arr_pos] = val
                    with open(bin_path, "wb") as f:
                        f.write(raw.tobytes())
                else:
                    print(f"  Position {arr_pos} out of range for {field} (len {len(raw)})")

if __name__ == "__main__":
    fix_index_data()
