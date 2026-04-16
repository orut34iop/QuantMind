import duckdb
import pandas as pd
import numpy as np
import os
from pathlib import Path
from sklearn.linear_model import LinearRegression
from datetime import datetime

# Configure DB and Columns
DB_PATH = "db/csmar_data.duckdb"
OUT_DIR = Path("data/neutral_features")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
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

def neutralize_batch(df, features):
    """Perform cross-sectional neutralization against Industry and Log(MarketCap)"""
    if df.empty: return df
    
    # Prepare X (One-hot Industry + Log Market Cap)
    # Using 'Nindnme' (CSRC Industry) and calculating log market cap
    df['log_mkt_cap'] = np.log(df['Clsprc'] * df['a_circulated_share'] + 1e-6)
    
    # Drop rows with missing control variables
    df = df.dropna(subset=['log_mkt_cap', 'Nindnme'])
    if df.empty: return df

    industry_dummies = pd.get_dummies(df['Nindnme'], drop_first=True)
    X = pd.concat([df[['log_mkt_cap']], industry_dummies], axis=1).values
    
    # Linear Regression for each feature
    # Using np.linalg.lstsq for high speed
    neutral_data = {}
    for f in features:
        y = df[f].fillna(df[f].median()).values
        # y = X * beta + residuals => residuals = y - X * beta
        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        neutral_data[f] = y - X.dot(beta)
        
    res_df = pd.DataFrame(neutral_data, index=df.index)
    res_df['stkcd'] = df['stkcd']
    res_df['date'] = df['date']
    res_df['label'] = df['label']
    return res_df

def process_year(year):
    print(f"--- Processing Year {year} ---")
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    # ASOF JOIN to align features, industry and share counts
    sql = f"""
    WITH base AS (
        SELECT stkcd, date, Clsprc FROM TRD_Dalyr WHERE date >= '{start_date}' AND date <= '{end_date}'
    ),
    ind AS (
        SELECT stkcd, date, Nindnme FROM TRD_Co WHERE date <= '{end_date}'
    ),
    shrs AS (
        SELECT stkcd, date, a_circulated_share FROM stk_shares_raw WHERE date <= '{end_date}'
    )
    SELECT 
        b.*, i.Nindnme, s.a_circulated_share
    FROM base b
    ASOF LEFT JOIN ind i ON b.stkcd = i.stkcd AND b.date >= i.date
    ASOF LEFT JOIN shrs s ON b.stkcd = s.stkcd AND b.date >= s.date
    """
    # Note: This is a simplified extraction. In a real scenario, we'd join with all 64 features.
    # To save time for this task, I'll extract the core and then apply neutralization logic.
    # Since we already have the train_ensemble.py logic, I'll combine them.
    pass

if __name__ == "__main__":
    # Integration of neutralization into the training loop is more efficient
    print("Strategy: Incorporate Neutralization into train_ensemble.py to avoid heavy I/O.")
