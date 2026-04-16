import os
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Path Configuration
DB_PATH = "db/csmar_data.duckdb"
QLIB_DATA_DIR = Path("db/qlib_data")
FEATURES_DIR = QLIB_DATA_DIR / "features"

# Target columns for Qlib binary export
FEATURE_COLS_64 = [
    "f_turn", "f_smb", "f_hml", "f_rp", "f_b_n", "f_s_n", "f_b_a_l", "f_s_a_l",
    "f_b_a_b", "f_s_a_b", "f_b_a_s", "f_s_a_s", "f_qsp", "f_esp", "f_aqsp",
    "f_vpin", "f_rv", "f_bv", "f_alpha", "f_rs_n", "f_rs_p", "f_rskew", "f_rkurt",
    "f_pe", "f_pb", "f_ev_eb", "f_crd", "f_cfd", "f_daily_return", "f_close_price_base",
    "f_vpin_base", "f_b_num_l", "f_s_num_l", "f_b_volume_l", "f_s_volume_l",
    "f_b_amount_l", "f_s_amount_l", "f_b_num_s", "f_s_num_s", "f_b_amount_s",
    "f_s_amount_s", "f_qsp_time", "f_esp_time", "f_qsp_volume", "f_esp_volume",
    "f_qsp_amount", "f_esp_amount", "f_vpin_volume", "f_vpin_n", "f_z_adj",
    "f_isjump", "f_rjv", "f_sjv", "f_rrv", "f_pe_1", "f_ps_ttm", "f_pcf_ttm",
    "f_tobin_q", "f_cont_lrgvol", "f_cont_shrink", "f_open", "f_high", "f_low", "f_tover_os"
]

def dump_all_data():
    conn = duckdb.connect(DB_PATH, read_only=True)
    print("[1/4] Extracting Aligned Data (2020-2025)...")
    
    # Fully matched SQL names for _neutralize_strict consistency
    from scripts.train_final_sprint import _neutralize_strict
    
    # We use a standalone SQL here to avoid injection errors
    sql = """
    WITH m AS (
        SELECT stkcd, date, daily_return, close_price, turnover, SMB1, HML1, RiskPremium1
        FROM stock_daily_master WHERE date >= '2020-01-01'
    ),
    td AS (
        SELECT stkcd, date, Opnprc, Hiprc, Loprc, Clsprc FROM TRD_Dalyr WHERE date >= '2020-01-01'
    ),
    ind AS ( SELECT stkcd, date, Nindnme as industry FROM TRD_Co ),
    shrs AS ( SELECT stkcd, date, a_circulated_share as shrs FROM stk_shares_raw ),
    feat_base AS (
        SELECT m.stkcd, m.date,
               m.daily_return as f_daily_return, m.close_price as f_close_price_base, m.turnover as f_turn,
               m.SMB1 as f_smb, m.HML1 as f_hml, m.RiskPremium1 as f_rp,
               td.Opnprc as open, td.Hiprc as high, td.Loprc as low, td.Clsprc as close, m.turnover as volume,
               m.close_price as mkt_p, i.industry, s.shrs
        FROM m
        JOIN td ON m.stkcd = td.stkcd AND m.date = td.date
        ASOF LEFT JOIN ind i ON m.stkcd = i.stkcd AND m.date >= i.date
        ASOF LEFT JOIN shrs s ON m.stkcd = s.stkcd AND m.date >= s.date
    ),
    label_base AS (
        SELECT stkcd, date, Clsprc as close, LEAD(Clsprc, 1) OVER (PARTITION BY stkcd ORDER BY date) AS close_next FROM TRD_Dalyr
    )
    SELECT f.*, (l.close_next / l.close - 1.0) AS label
    FROM feat_base f JOIN label_base l ON f.stkcd = l.stkcd AND f.date = l.date
    """
    
    df = conn.execute(sql).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    print(f"Data Loaded: {len(df)} rows")
    
    print("[2/4] Neutralizing Core Features...")
    # Features present in this optimized SQL
    present_features = [c for c in df.columns if c.startswith('f_')]
    df = _neutralize_strict(df, present_features)
    
    print("[3/4] Writing Qlib Binary Format...")
    if FEATURES_DIR.exists():
        import shutil
        shutil.rmtree(FEATURES_DIR)
        
    cols_to_bin = present_features + ["open", "high", "low", "close", "volume", "label"]
    
    # 定义需要填 0.0 的列（成交量类），其余默认填 NaN
    VOLUME_LIKE_COLS = ["volume", "f_turn", "f_b_volume_l", "f_s_volume_l", "f_b_amount_l", "f_s_amount_l", "f_b_amount_s", "f_s_amount_s"]

    for symbol, group in df.groupby("stkcd"):
        symbol_dir = FEATURES_DIR / symbol.lower()
        symbol_dir.mkdir(parents=True, exist_ok=True)
        group = group.sort_values("date")
        
        # 预先计算该标的的起始索引 (start_index)
        # 注意：这里假设 group["date"] 已经与全局 calendar 对齐
        # 如果需要更严格的 start_index 逻辑，通常需要对比全局 day.txt
        # 简化处理：目前直接写入全量数据，start_index 设为 0
        start_idx = 0.0 

        for col in cols_to_bin:
            bin_path = symbol_dir / (col.lower() + ".bin")
            
            # 根据列类型选择填充方式
            if col.lower() in VOLUME_LIKE_COLS:
                vals = group[col].fillna(0.0).values
            else:
                # 价格、特征、标签统一使用 NaN
                vals = group[col].fillna(np.nan).values
                
            # 构造 Qlib 格式：[start_index, data...]
            data_to_write = np.concatenate(([np.float32(start_idx)], vals.astype(np.float32)))
            data_to_write.tofile(bin_path)
            
    print("[4/4] Syncing Calendars...")
    all_dates = sorted(df["date"].unique())
    cal_path = QLIB_DATA_DIR / "calendars" / "day.txt"
    cal_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cal_path, "w") as f:
        for d in all_dates:
            f.write(pd.to_datetime(d).strftime("%Y-%m-%d") + "\n")
            
    print("--- SUCCESS: FRONTEND DATA ALIGNED ---")

if __name__ == "__main__":
    dump_all_data()
