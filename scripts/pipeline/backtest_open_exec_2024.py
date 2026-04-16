import pandas as pd
import numpy as np
import lightgbm as lgb
import duckdb
import os

# Configuration
DB_PATH = "data/official_data.duckdb"
MODEL_PATH = "models/production/model_qlib/model.txt"
TOP_K = 50
INITIAL_CASH = 1000000
COST = 0.0005 # 5BP round-trip

def run_open_price_backtest_2024():
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # 核心 SQL：引入开盘价执行逻辑
    # 我们需要获取 T+1 Open 到 T+2 Open 的收益率
    query = """
    WITH master AS (
        SELECT 
            stkcd, date, 
            Opnprc as open, 
            Clsprc as close,
            daily_return as ret_close_to_close
        FROM TRD_Dalyr
        GROUP BY stkcd, date, Opnprc, Clsprc, daily_return
    ),
    -- 计算真正的 T+1 Open 到 T+2 Open 收益率
    execution_rets AS (
        SELECT 
            stkcd, date,
            -- 下一交易日开盘买入，再下一交易日开盘卖出的收益率
            -- (Next Open / Current Open) - 1 is not correct. 
            -- We need (T+2 Open / T+1 Open) - 1
            LEAD(open, 2) OVER (PARTITION BY stkcd ORDER BY date) / NULLIF(LEAD(open, 1) OVER (PARTITION BY stkcd ORDER BY date), 0) - 1 as label_open_to_open
        FROM master
    ),
    -- 提取模型特征 (Lag 1)
    features_data AS (
        SELECT 
            m.stkcd, m.date,
            LAG(m.turn) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_turn,
            LAG(m.smb) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_smb,
            LAG(m.hml) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_hml,
            LAG(m.rp) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rp,
            LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_b_n,
            LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_s_n,
            LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_b_a_l,
            LAG(bs.vol_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_s_a_l,
            LAG(bs.b_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_b_a_b,
            LAG(bs.s_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_s_a_b,
            LAG(bs.b_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_b_a_s,
            LAG(bs.s_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_s_a_s,
            LAG(sp.qsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_qsp,
            LAG(sp.esp) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_esp,
            LAG(sp.aqsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_aqsp,
            LAG(vpin.vpin) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_vpin,
            LAG(sj.rv) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rv,
            LAG(sj.bv) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_bv,
            LAG(sj.alpha) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_alpha,
            LAG(sj.rs_n) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rs_n,
            LAG(sj.rs_p) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rs_p,
            LAG(sr.rskew) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rskew,
            LAG(sr.rkurt) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_rkurt,
            LAG(val.pe) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_pe,
            LAG(val.pb) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_pb,
            LAG(val.ev_eb) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_ev_eb,
            LAG(trend.crd) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_crd,
            LAG(trend.cfd) OVER (PARTITION BY m.stkcd ORDER BY m.date) as f_cfd,
            m.close as close_price
        FROM (SELECT stkcd, date, AVG(turnover) as turn, AVG(SMB1) as smb, AVG(HML1) as hml, AVG(RiskPremium1) as rp, AVG(Clsprc) as close FROM stock_daily_master GROUP BY stkcd, date) m
        LEFT JOIN (SELECT stkcd, date, AVG(B_Amount_L - S_Amount_L) as inflow_L, AVG(B_Num_L) as num_L, AVG(B_Volume_L) as vol_L, AVG(B_Amount_B) as b_a_b, AVG(S_Amount_B) as s_a_b, AVG(B_Amount_S) as b_a_s, AVG(S_Amount_S) as s_a_s FROM HF_BSImbalance GROUP BY stkcd, date) bs ON m.stkcd = bs.stkcd AND m.date = bs.date
        LEFT JOIN (SELECT stkcd, date, AVG(Qsp_equal) as qsp, AVG(Esp_equal) as esp, AVG(AQsp_equal) as aqsp FROM HF_Spread GROUP BY stkcd, date) sp ON m.stkcd = sp.stkcd AND m.date = sp.date
        LEFT JOIN (SELECT stkcd, date, AVG(TRY_CAST(VPIN AS DOUBLE)) as vpin FROM HF_VPIN GROUP BY stkcd, date) vpin ON m.stkcd = vpin.stkcd AND m.date = vpin.date
        LEFT JOIN (SELECT stkcd, date, AVG(RV) as rv, AVG(BV) as bv, AVG(TRY_CAST(Alpha AS DOUBLE)) as alpha, AVG(RS_N) as rs_n, AVG(RS_P) as rs_p FROM HF_StockJump GROUP BY stkcd, date) sj ON m.stkcd = sj.stkcd AND m.date = sj.date
        LEFT JOIN (SELECT stkcd, date, AVG(RSkew) as rskew, AVG(RKurt) as rkurt FROM HF_StockRealized GROUP BY stkcd, date) sr ON m.stkcd = sr.stkcd AND m.date = sr.date
        LEFT JOIN (SELECT stkcd, date, AVG(pe_ratio_ttm) as pe, AVG(pb_ratio) as pb, AVG(ev_ebitda_ttm) as ev_eb FROM stk_valuation_raw GROUP BY stkcd, date) val ON m.stkcd = val.stkcd AND m.date = val.date
        LEFT JOIN (SELECT stkcd, date, AVG(TRY_CAST(ContinuedRiseDays AS DOUBLE)) as crd, AVG(TRY_CAST(ContinuedFallDays AS DOUBLE)) as cfd FROM TRD_StockTrend GROUP BY stkcd, date) trend ON m.stkcd = trend.stkcd AND m.date = trend.date
    )

    SELECT 
        f.*,
        e.label_open_to_open
    FROM features_data f
    JOIN execution_rets e ON f.stkcd = e.stkcd AND f.date = e.date
    WHERE f.date >= '2024-01-01' AND f.date <= '2024-12-31'
    """
    
    print("Extracting 2024 data with Next-Day Open Execution logic...")
    df = conn.execute(query).df()
    df = df.dropna(subset=['label_open_to_open'])
    df['label_open_to_open'] = df['label_open_to_open'].clip(-0.1, 0.1)
    
    # 2. 生成预测
    model = lgb.Booster(model_file=MODEL_PATH)
    feature_cols = [c for c in df.columns if c.startswith('f_')] + ['close_price']
    df['score'] = model.predict(df[feature_cols].values)
    
    # 3. 运行 Top 50 回测 (每日 100% 换手，最严酷)
    records = []
    dates = sorted(df['date'].unique())
    for d in dates:
        day_data = df[df['date'] == d].sort_values('score', ascending=False).head(TOP_K)
        day_ret = day_data['label_open_to_open'].mean()
        # 假设每日全调仓 100% 换手，成本 5BP
        records.append(day_ret - COST)
        
    perf = pd.Series(records)
    eq = (1 + perf).cumprod()
    
    print("
========================================")
    print("   2024 TOP-50 OPEN-PRICE EXECUTION")
    print("========================================")
    print(f"Total Return:   {eq.iloc[-1]-1:.2%}")
    print(f"Sharpe Ratio:   {perf.mean()*252/(perf.std()*np.sqrt(252)):.2f}")
    print(f"Max Drawdown:   {(eq/eq.cummax()-1).min():.2%}")
    print("========================================
")
    
    # Clean up right away per new rule
    conn.close()

if __name__ == "__main__":
    run_open_price_backtest_2024()
