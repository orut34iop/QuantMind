#!/usr/bin/env python3
"""Extract QuantMind ~150 feature snapshot from official factors DuckDB.

默认先用于 2016 年测试提取。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract model training feature snapshot")
    p.add_argument("--db", default="db/official_factors.duckdb")
    p.add_argument("--catalog", default="config/features/model_training_feature_catalog_v1.json")
    p.add_argument("--year", type=int, default=2016)
    p.add_argument("--out-parquet", default="data/feature_snapshots/features_{year}.parquet")
    p.add_argument("--out-report", default="data/feature_snapshots/model_features_{year}_report.json")
    p.add_argument("--sample-limit", type=int, default=0)
    return p.parse_args()


def load_catalog(path: str) -> list[str]:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    keys: list[str] = []
    for cat in obj.get("categories", []):
        for feat in cat.get("features", []):
            k = str(feat.get("key", "")).strip()
            if k:
                keys.append(k)
    return keys


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    feature_keys = load_catalog(args.catalog)

    out_parquet = Path(args.out_parquet.format(year=args.year))
    out_report = Path(args.out_report.format(year=args.year))
    ensure_parent(out_parquet)
    ensure_parent(out_report)

    con = duckdb.connect(args.db)
    con.execute("PRAGMA threads=16")
    con.execute("PRAGMA temp_directory='tmp'")
    con.execute("PRAGMA max_temp_directory_size='500GiB'")
    con.execute("PRAGMA memory_limit='80GB'")

    # --- Stage 1: Base Table & Simple Daily Stats ---
    print(f">>> [{args.year}] Stage 1: Base features extraction (with deduplication)...")
    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE stage1_base AS
    WITH raw_base AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        CASE
          WHEN LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '6%' THEN 'SH' || LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0')
          WHEN LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '0%' OR LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '3%' THEN 'SZ' || LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0')
        END AS symbol,
        Trddt AS trade_date,
        Opnprc * (Adjprcwd / NULLIF(Clsprc, 0)) AS open_price,
        Hiprc * (Adjprcwd / NULLIF(Clsprc, 0)) AS high_price,
        Loprc * (Adjprcwd / NULLIF(Clsprc, 0)) AS low_price,
        Adjprcwd AS close_price,
        Dnshrtrd AS volume,
        Dnvaltrd AS amount,
        ChangeRatio AS ret_1d,
        Dsmvtll AS market_value,
        Dsmvosd AS circulated_market_value
      FROM "日个股回报率文件"
      WHERE Trddt BETWEEN DATE '{args.year}-01-01' AND DATE '{args.year}-12-31'
        AND (
          LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '6%' OR
          LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '0%' OR
          LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '3%'
        )
        AND LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') NOT LIKE '900%'
        AND LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') NOT LIKE '200%'
    ),
    turnover AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date, 
        AVG(ToverOs) AS tover_os, 
        AVG(ToverTl) AS tover_tl
      FROM "个股换手率表日"
      GROUP BY 1,2
    ),
    trdstat AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date,
        SUM(Toltrdtims) AS trade_count,
        SUM(Tolstknva) AS total_trade_amount
      FROM "日交易统计文件"
      GROUP BY 1,2
    ),
    company AS (
      SELECT LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6, MAX(Indcd) AS indcd
      FROM "公司文件"
      GROUP BY 1
    )
    SELECT 
      b.*,
      t.tover_os, t.tover_tl,
      ts.trade_count, ts.total_trade_amount,
      c.indcd
    FROM raw_base b
    LEFT JOIN turnover t USING(symbol6, trade_date)
    LEFT JOIN trdstat ts USING(symbol6, trade_date)
    LEFT JOIN company c USING(symbol6)
    """)

    # --- Stage 2: High Frequency Intraday Metrics (Deduplicated) ---
    print(f">>> [{args.year}] Stage 2: Joining intraday high-frequency metrics...")
    con.execute("""
    CREATE OR REPLACE TEMP TABLE stage2_hf AS
    WITH imb AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date,
        AVG(B_Num) AS B_Num, AVG(S_Num) AS S_Num, 
        AVG(B_Volume) AS B_Volume, AVG(S_Volume) AS S_Volume, 
        AVG(B_Amount) AS B_Amount, AVG(S_Amount) AS S_Amount,
        AVG(B_Num_L) AS B_Num_L, AVG(S_Num_L) AS S_Num_L, 
        AVG(B_Volume_L) AS B_Volume_L, AVG(S_Volume_L) AS S_Volume_L, 
        AVG(B_Amount_L) AS B_Amount_L, AVG(S_Amount_L) AS S_Amount_L,
        AVG(B_Num_M) AS B_Num_M, AVG(S_Num_M) AS S_Num_M, 
        AVG(B_Volume_M) AS B_Volume_M, AVG(S_Volume_M) AS S_Volume_M, 
        AVG(B_Amount_M) AS B_Amount_M, AVG(S_Amount_M) AS S_Amount_M,
        AVG(B_Num_S) AS B_Num_S, AVG(S_Num_S) AS S_Num_S, 
        AVG(B_Volume_S) AS B_Volume_S, AVG(S_Volume_S) AS S_Volume_S, 
        AVG(B_Amount_S) AS B_Amount_S, AVG(S_Amount_S) AS S_Amount_S
      FROM "个股买卖不平衡指标表日"
      GROUP BY 1,2
    ),
    spread AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date,
        AVG(Qsp_equal) AS Qsp_equal, AVG(Esp_equal) AS Esp_equal, AVG(AQsp_equal) AS AQsp_equal,
        AVG(Qsp_time) AS Qsp_time, AVG(Esp_time) AS Esp_time,
        AVG(Qsp_Volume) AS Qsp_Volume, AVG(Esp_Volume) AS Esp_Volume,
        AVG(Qsp_Amount) AS Qsp_Amount, AVG(Esp_Amount) AS Esp_Amount
      FROM "个股买卖价差表日"
      GROUP BY 1,2
    ),
    vpin AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date,
        AVG(VPIN) AS VPIN
      FROM "个股知情交易概率指标表日"
      GROUP BY 1,2
    ),
    realized AS (
      SELECT 
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date, 
        AVG(RV) AS RV, AVG(RRV) AS RRV, AVG(RSkew) AS RSkew, AVG(RKurt) AS RKurt
      FROM "个股已实现指标表日"
      GROUP BY 1,2
    ),
    jump AS (
      SELECT
        LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') AS symbol6,
        Trddt AS trade_date,
        AVG(Z_Adj) AS z_adj, AVG(RJV) AS rjv, AVG(SJV) AS sjv, MAX(ISJump) AS is_jump
      FROM "个股跳跃指标表日"
      GROUP BY 1,2
    )
    SELECT 
      s1.*,
      i.* EXCLUDE(symbol6, trade_date),
      s.* EXCLUDE(symbol6, trade_date),
      v.VPIN,
      r.RV, r.RRV, r.RSkew, r.RKurt,
      j.z_adj, j.rjv, j.sjv, j.is_jump
    FROM stage1_base s1
    LEFT JOIN imb i USING(symbol6, trade_date)
    LEFT JOIN spread s USING(symbol6, trade_date)
    LEFT JOIN vpin v USING(symbol6, trade_date)
    LEFT JOIN realized r USING(symbol6, trade_date)
    LEFT JOIN jump j USING(symbol6, trade_date)
    """)

    # --- Stage 3: Market Factors & Valuation (Deduplicated) ---
    print(f">>> [{args.year}] Stage 3: Joining market factors and valuation...")
    con.execute("""
    CREATE OR REPLACE TEMP TABLE stage3_market AS
    WITH ff3 AS (
      SELECT
        TradingDate AS trade_date,
        AVG(RiskPremium1) AS mkt_premium,
        AVG(SMB1) AS smb1,
        AVG(HML1) AS hml1
      FROM "三因子模型指标日"
      GROUP BY 1
    ),
    val_src AS (
      SELECT
        LPAD(COALESCE(RIGHT(CAST(Stkcd AS VARCHAR), 6), LPAD(CAST(stock_code AS VARCHAR), 6, '0')), 6, '0') AS symbol6,
        COALESCE(date, Accper) AS report_date,
        AVG(COALESCE(pb_ratio, F100201B)) AS pb_ratio,
        AVG(COALESCE(pe_ratio_ttm, F100101B)) AS pe_ratio_ttm,
        AVG(F100801A) AS f_sp,
        AVG(F100901A) AS f_cfp,
        AVG(F100601B) AS f_ev_ebitda,
        AVG(F101001A) AS f_tobin_q
      FROM "相对价值指标"
      WHERE COALESCE(date, Accper) IS NOT NULL
      GROUP BY 1,2
    ),
    val_daily AS (
      SELECT
        s2.symbol6,
        s2.trade_date,
        LAST_VALUE(v.pb_ratio IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS pb_ratio,
        LAST_VALUE(v.pe_ratio_ttm IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS pe_ratio_ttm,
        LAST_VALUE(v.f_sp IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS f_sp,
        LAST_VALUE(v.f_cfp IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS f_cfp,
        LAST_VALUE(v.f_ev_ebitda IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS f_ev_ebitda,
        LAST_VALUE(v.f_tobin_q IGNORE NULLS) OVER (PARTITION BY s2.symbol6 ORDER BY s2.trade_date) AS f_tobin_q
      FROM stage2_hf s2
      LEFT JOIN val_src v ON s2.symbol6 = v.symbol6 AND s2.trade_date = v.report_date
    )
    SELECT 
      s2.*,
      f.mkt_premium, f.smb1, f.hml1,
      vd.pb_ratio, vd.pe_ratio_ttm, vd.f_sp, vd.f_cfp, vd.f_ev_ebitda, vd.f_tobin_q
    FROM stage2_hf s2
    LEFT JOIN ff3 f USING(trade_date)
    LEFT JOIN val_daily vd USING(symbol6, trade_date)
    """)

    # --- Stage 4: Final Calculations (Window Functions) ---
    print(f">>> [{args.year}] Stage 4: Executing complex window functions...")
    sql = f"""
    CREATE OR REPLACE TEMP TABLE feature_snapshot_raw AS
    WITH calc1 AS (
      SELECT
        *,
        LAG(close_price, 1) OVER w AS lag_close_1,
        LAG(close_price, 3) OVER w AS lag_close_3,
        LAG(close_price, 5) OVER w AS lag_close_5,
        LAG(close_price,10) OVER w AS lag_close_10,
        LAG(close_price,12) OVER w AS lag_close_12,
        LAG(close_price,20) OVER w AS lag_close_20,
        LAG(close_price,60) OVER w AS lag_close_60,
        LAG(close_price,120) OVER w AS lag_close_120,
        AVG(close_price) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5,
        AVG(close_price) OVER (w ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS ma10,
        AVG(close_price) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma20,
        AVG(close_price) OVER (w ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ma60,
        AVG(close_price) OVER (w ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS ma120,
        AVG(close_price) OVER (w ROWS BETWEEN 11 PRECEDING AND CURRENT ROW) AS ema12,
        AVG(close_price) OVER (w ROWS BETWEEN 25 PRECEDING AND CURRENT ROW) AS ema26,
        STDDEV_POP(ret_1d) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS std5,
        STDDEV_POP(ret_1d) OVER (w ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS std10,
        STDDEV_POP(ret_1d) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS std20,
        STDDEV_POP(ret_1d) OVER (w ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS std60,
        GREATEST(
          high_price - low_price,
          ABS(high_price - LAG(close_price, 1) OVER w),
          ABS(low_price - LAG(close_price, 1) OVER w)
        ) AS tr,
        LN(NULLIF(high_price,0) / NULLIF(low_price,0)) AS ln_hl,
        LN(NULLIF(close_price,0) / NULLIF(open_price,0)) AS ln_co,
        LN(NULLIF(high_price,0) / NULLIF(open_price,0)) AS ln_ho,
        LN(NULLIF(low_price,0) / NULLIF(open_price,0)) AS ln_lo,
        LN(NULLIF(high_price,0) / NULLIF(close_price,0)) AS ln_hc,
        LN(NULLIF(low_price,0) / NULLIF(close_price,0)) AS ln_lc,
        AVG(volume) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS vol_ma5,
        AVG(volume) OVER (w ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS vol_ma10,
        AVG(volume) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_ma20,
        AVG(amount) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS amt_ma5,
        AVG(amount) OVER (w ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS amt_ma10,
        AVG(amount) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amt_ma20,
        LAG(close_price, 1) OVER w AS prev_close_price,
        amount * (((close_price - low_price) - (high_price - close_price)) / NULLIF(high_price - low_price, 0)) AS mfv,
        ((high_price + low_price + close_price) / 3.0) AS typ_price,
        AVG(vpin) OVER (w ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS vpin_ma5,
        AVG(vpin) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vpin_ma20,
        vpin - LAG(vpin,5) OVER w AS vpin_delta5,
        AVG(ret_1d) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ind_ret_5d,
        AVG(ret_1d) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW) AS ind_ret_10d,
        AVG(ret_1d) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ind_ret_20d,
        AVG(ret_1d) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS ind_ret_60d,
        STDDEV_POP(ret_1d) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ind_vol_20d,
        AVG(tover_os) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ind_tover_20d,
        AVG(amount) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ind_amt_20d,
        AVG(B_Amount - S_Amount) OVER (PARTITION BY indcd ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ind_flow_20d,
        AVG(ret_1d) OVER (PARTITION BY indcd, trade_date) AS ind_ret_1d,
        STDDEV_POP(ret_1d) OVER (PARTITION BY indcd, trade_date) AS ind_disp,
        AVG(volume) OVER (PARTITION BY indcd, trade_date) AS ind_vol_1d,
        SUM(CASE WHEN ret_1d > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY indcd, trade_date) * 1.0 /
          NULLIF(COUNT(*) OVER (PARTITION BY indcd, trade_date),0) AS ind_up_breadth,
        SUM(CASE WHEN ret_1d < 0 THEN 1 ELSE 0 END) OVER (PARTITION BY indcd, trade_date) * 1.0 /
          NULLIF(COUNT(*) OVER (PARTITION BY indcd, trade_date),0) AS ind_down_breadth
      FROM stage3_market
      WINDOW w AS (PARTITION BY symbol ORDER BY trade_date)
    ),
    calc2 AS (
      SELECT
        *,
        SUM(CASE WHEN close_price > prev_close_price THEN volume
                 WHEN close_price < prev_close_price THEN -volume
                 ELSE 0 END)
          OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS obv_cum,
        LAG(typ_price,1) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_typ_price,
        ema12 - ema26 AS macd_dif,
        AVG(ema12 - ema26) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW) AS macd_dea,
        100 - (100 / (1 + (
          AVG(CASE WHEN ret_1d > 0 THEN ret_1d ELSE 0 END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)
          /
          NULLIF(ABS(AVG(CASE WHEN ret_1d < 0 THEN ret_1d ELSE 0 END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW)),0)
        ))) AS rsi6,
        100 - (100 / (1 + (
          AVG(CASE WHEN ret_1d > 0 THEN ret_1d ELSE 0 END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)
          /
          NULLIF(ABS(AVG(CASE WHEN ret_1d < 0 THEN ret_1d ELSE 0 END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW)),0)
        ))) AS rsi14,
        100 * (close_price - MIN(low_price) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW))
          / NULLIF(MAX(high_price) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW)
          - MIN(low_price) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 8 PRECEDING AND CURRENT ROW),0) AS rsv,
        AVG(tr) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS atr14,
        AVG(tr) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS atr20,
        SQRT(GREATEST(AVG((ln_hl * ln_hl)/(4*LN(2))) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0)) AS park10,
        SQRT(GREATEST(AVG((ln_hl * ln_hl)/(4*LN(2))) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0)) AS park20,
        SQRT(GREATEST(AVG(0.5*ln_hl*ln_hl - (2*LN(2)-1)*ln_co*ln_co) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0)) AS gk10,
        SQRT(GREATEST(AVG(0.5*ln_hl*ln_hl - (2*LN(2)-1)*ln_co*ln_co) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0)) AS gk20,
        SQRT(GREATEST(AVG((ln_ho*ln_hc + ln_lo*ln_lc)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 9 PRECEDING AND CURRENT ROW), 0)) AS rs10,
        SQRT(GREATEST(AVG((ln_ho*ln_hc + ln_lo*ln_lc)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW), 0)) AS rs20,
        STDDEV_POP(CASE WHEN ret_1d < 0 THEN ret_1d END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS downside20,
        STDDEV_POP(CASE WHEN ret_1d > 0 THEN ret_1d END) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS upside20,
        SUM(mfv) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ad_cum,
        typ_price * volume AS raw_money_flow,
        COVAR_POP(ret_1d, mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) /
          NULLIF(VAR_POP(mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),0) AS beta20,
        COVAR_POP(ret_1d, mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) /
          NULLIF(VAR_POP(mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW),0) AS beta60,
        COVAR_POP(ret_1d, mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) /
          NULLIF(VAR_POP(mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW),0) AS beta120
      FROM calc1
    ),
    calc3 AS (
      SELECT
        *,
        AVG(rsv) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS kdj_k,
        obv_cum - LAG(obv_cum,20) OVER (PARTITION BY symbol ORDER BY trade_date) AS obv20,
        obv_cum - LAG(obv_cum,60) OVER (PARTITION BY symbol ORDER BY trade_date) AS obv60,
        ad_cum - LAG(ad_cum,20) OVER (PARTITION BY symbol ORDER BY trade_date) AS accdist20,
        AVG(ABS(ret_1d)/NULLIF(amount,0)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS amihud20,
        AVG(ABS(ret_1d)/NULLIF(amount,0)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS amihud60,
        SUM(CASE WHEN typ_price > prev_typ_price THEN raw_money_flow ELSE 0 END)
          OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS pos_mf14,
        SUM(CASE WHEN typ_price < prev_typ_price THEN raw_money_flow ELSE 0 END)
          OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) AS neg_mf14,
        AVG(B_Amount - S_Amount) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mean_flow60,
        STDDEV_POP(B_Amount - S_Amount) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS std_flow60,
        AVG(vpin) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mean_vpin60,
        STDDEV_POP(vpin) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS std_vpin60,
        AVG(Esp_equal) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mean_esp60,
        STDDEV_POP(Esp_equal) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS std_esp60,
        AVG((B_Amount - S_Amount) / NULLIF(B_Amount + S_Amount,0)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mean_imb60,
        STDDEV_POP((B_Amount - S_Amount) / NULLIF(B_Amount + S_Amount,0)) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS std_imb60,
        AVG(1 / NULLIF(pb_ratio,0)) OVER (PARTITION BY indcd, trade_date) AS ind_avg_bp,
        AVG(market_value) OVER (PARTITION BY indcd, trade_date) AS ind_avg_mv
      FROM calc2
    ),
    calc4 AS (
      SELECT
        *,
        AVG(kdj_k) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS kdj_d
      FROM calc3
    ),
    final_calc AS (
      SELECT
        symbol,
        trade_date,
        open_price AS open,
        high_price AS high,
        low_price AS low,
        close_price AS close,
        volume AS volume,
        1.0 AS factor,
        mom_ret_1d, mom_ret_3d, mom_ret_5d, mom_ret_10d, mom_ret_20d, mom_ret_60d, mom_ret_120d,
        mom_ma_gap_5, mom_ma_gap_10, mom_ma_gap_20, mom_ma_gap_60, mom_ma_gap_120,
        mom_ema_gap_12, mom_ema_gap_26,
        mom_macd_dif, mom_macd_dea, mom_macd_hist,
        mom_rsi_6, mom_rsi_14, mom_kdj_k, mom_kdj_d, mom_kdj_j,
        mom_roc_12, mom_breakout_20d,
        vol_std_5, vol_std_10, vol_std_20, vol_std_60,
        vol_atr_14, vol_atr_20, vol_true_range,
        vol_parkinson_10, vol_parkinson_20, vol_gk_10, vol_gk_20, vol_rs_10, vol_rs_20,
        vol_downside_20, vol_upside_20, vol_realized_rv, vol_realized_rrv, vol_realized_rskew, vol_realized_rkurt,
        vol_jump_zadj, vol_jump_rjv_ratio, vol_jump_sjv_ratio,
        liq_turnover_os, liq_turnover_tl, liq_volume, liq_volume_ma_5, liq_volume_ma_10, liq_volume_ma_20,
        liq_volume_ratio_5, liq_volume_ratio_20, liq_amount, liq_amount_ma_5, liq_amount_ma_10, liq_amount_ma_20,
        liq_amount_ratio_5, liq_amount_ratio_20, liq_trade_count, liq_avg_trade_size,
        liq_obv_20, liq_obv_60, liq_mfi_14, liq_accdist_20, liq_amihud_20, liq_amihud_60,
        flow_net_amount, flow_net_amount_ratio, flow_large_net_amount, flow_large_net_ratio,
        flow_medium_net_amount, flow_medium_net_ratio, flow_small_net_amount, flow_small_net_ratio,
        flow_net_order_count, flow_net_order_ratio, flow_large_net_order, flow_large_order_ratio,
        flow_vpin, flow_vpin_ma_5, flow_vpin_ma_20, flow_vpin_delta_5,
        flow_qsp, flow_esp, flow_aqsp, flow_qsp_time, flow_esp_time, flow_pressure_index,
        style_ln_mv_total, style_ln_mv_float, style_bp, style_ep_ttm, style_sp_ttm, style_cfp_ttm,
        style_ev_ebitda_ttm, style_tobin_q, style_smb, style_hml, style_mkt_premium,
        style_beta_20, style_beta_60, style_beta_120, style_idio_vol_20, style_idio_vol_60, style_residual_ret_20,
        style_valuation_composite, style_size_percentile, style_value_percentile,
        ind_ret_1d, ind_ret_5d, ind_ret_10d, ind_ret_20d, ind_vol_20, ind_turnover_20, ind_amount_20,
        ind_strength_20, ind_strength_60, ind_dispersion_20, ind_up_breadth_20, ind_down_breadth_20,
        ind_relative_volume_20, ind_relative_volatility_20, ind_relative_flow_20, ind_momentum_rank_20,
        ind_value_rank, ind_size_rank, ind_code_l1, ind_code_l2,
        micro_qsp_equal, micro_esp_equal, micro_aqsp_equal, micro_qsp_time, micro_esp_time,
        micro_qsp_volume, micro_esp_volume, micro_qsp_amount, micro_esp_amount,
        micro_effective_spread, micro_quoted_spread, micro_spread_vol_20,
        micro_imbalance_volume, micro_imbalance_amount, micro_imbalance_count,
        micro_imbalance_large, micro_imbalance_medium, micro_imbalance_small,
        micro_jump_flag, micro_pressure_score
      FROM (
        SELECT
          *,
          (close_price / NULLIF(lag_close_1,0) - 1) AS mom_ret_1d,
          (close_price / NULLIF(lag_close_3,0) - 1) AS mom_ret_3d,
          (close_price / NULLIF(lag_close_5,0) - 1) AS mom_ret_5d,
          (close_price / NULLIF(lag_close_10,0) - 1) AS mom_ret_10d,
          (close_price / NULLIF(lag_close_20,0) - 1) AS mom_ret_20d,
          (close_price / NULLIF(lag_close_60,0) - 1) AS mom_ret_60d,
          (close_price / NULLIF(lag_close_120,0) - 1) AS mom_ret_120d,
          (close_price / NULLIF(ma5,0) - 1) AS mom_ma_gap_5,
          (close_price / NULLIF(ma10,0) - 1) AS mom_ma_gap_10,
          (close_price / NULLIF(ma20,0) - 1) AS mom_ma_gap_20,
          (close_price / NULLIF(ma60,0) - 1) AS mom_ma_gap_60,
          (close_price / NULLIF(ma120,0) - 1) AS mom_ma_gap_120,
          (close_price / NULLIF(ema12,0) - 1) AS mom_ema_gap_12,
          (close_price / NULLIF(ema26,0) - 1) AS mom_ema_gap_26,
          macd_dif AS mom_macd_dif,
          macd_dea AS mom_macd_dea,
          2*(macd_dif-macd_dea) AS mom_macd_hist,
          rsi6 AS mom_rsi_6,
          rsi14 AS mom_rsi_14,
          kdj_k AS mom_kdj_k,
          kdj_d AS mom_kdj_d,
          3*kdj_k - 2*kdj_d AS mom_kdj_j,
          (close_price / NULLIF(lag_close_12,0) - 1) AS mom_roc_12,
          (close_price / NULLIF(MAX(high_price) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW),0) - 1) AS mom_breakout_20d,
          std5 AS vol_std_5,
          std10 AS vol_std_10,
          std20 AS vol_std_20,
          std60 AS vol_std_60,
          atr14 AS vol_atr_14,
          atr20 AS vol_atr_20,
          tr AS vol_true_range,
          park10 AS vol_parkinson_10,
          park20 AS vol_parkinson_20,
          gk10 AS vol_gk_10,
          gk20 AS vol_gk_20,
          rs10 AS vol_rs_10,
          rs20 AS vol_rs_20,
          downside20 AS vol_downside_20,
          upside20 AS vol_upside_20,
          rv AS vol_realized_rv,
          rrv AS vol_realized_rrv,
          rskew AS vol_realized_rskew,
          rkurt AS vol_realized_rkurt,
          z_adj AS vol_jump_zadj,
          rjv / NULLIF(rv,0) AS vol_jump_rjv_ratio,
          sjv / NULLIF(rv,0) AS vol_jump_sjv_ratio,
          tover_os AS liq_turnover_os,
          tover_tl AS liq_turnover_tl,
          volume AS liq_volume,
          vol_ma5 AS liq_volume_ma_5,
          vol_ma10 AS liq_volume_ma_10,
          vol_ma20 AS liq_volume_ma_20,
          volume / NULLIF(vol_ma5,0) AS liq_volume_ratio_5,
          volume / NULLIF(vol_ma20,0) AS liq_volume_ratio_20,
          amount AS liq_amount,
          amt_ma5 AS liq_amount_ma_5,
          amt_ma10 AS liq_amount_ma_10,
          amt_ma20 AS liq_amount_ma_20,
          amount / NULLIF(amt_ma5,0) AS liq_amount_ratio_5,
          amount / NULLIF(amt_ma20,0) AS liq_amount_ratio_20,
          trade_count AS liq_trade_count,
          total_trade_amount / NULLIF(trade_count,0) AS liq_avg_trade_size,
          obv20 AS liq_obv_20,
          obv60 AS liq_obv_60,
          100 - (100 / (1 + pos_mf14/NULLIF(neg_mf14,0))) AS liq_mfi_14,
          accdist20 AS liq_accdist_20,
          amihud20 AS liq_amihud_20,
          amihud60 AS liq_amihud_60,
          (B_Amount - S_Amount) AS flow_net_amount,
          (B_Amount - S_Amount) / NULLIF(B_Amount + S_Amount,0) AS flow_net_amount_ratio,
          (B_Amount_L - S_Amount_L) AS flow_large_net_amount,
          (B_Amount_L - S_Amount_L) / NULLIF(B_Amount_L + S_Amount_L,0) AS flow_large_net_ratio,
          (B_Amount_M - S_Amount_M) AS flow_medium_net_amount,
          (B_Amount_M - S_Amount_M) / NULLIF(B_Amount_M + S_Amount_M,0) AS flow_medium_net_ratio,
          (B_Amount_S - S_Amount_S) AS flow_small_net_amount,
          (B_Amount_S - S_Amount_S) / NULLIF(B_Amount_S + S_Amount_S,0) AS flow_small_net_ratio,
          (B_Num - S_Num) AS flow_net_order_count,
          (B_Num - S_Num) / NULLIF(B_Num + S_Num,0) AS flow_net_order_ratio,
          (B_Num_L - S_Num_L) AS flow_large_net_order,
          (B_Num_L - S_Num_L) / NULLIF(B_Num_L + S_Num_L,0) AS flow_large_order_ratio,
          vpin AS flow_vpin,
          vpin_ma5 AS flow_vpin_ma_5,
          vpin_ma20 AS flow_vpin_ma_20,
          vpin_delta5 AS flow_vpin_delta_5,
          Qsp_equal AS flow_qsp,
          Esp_equal AS flow_esp,
          AQsp_equal AS flow_aqsp,
          Qsp_time AS flow_qsp_time,
          Esp_time AS flow_esp_time,
          ((B_Amount - S_Amount) - mean_flow60) / NULLIF(std_flow60,0)
            + (vpin - mean_vpin60) / NULLIF(std_vpin60,0)
            + (Esp_equal - mean_esp60) / NULLIF(std_esp60,0) AS flow_pressure_index,
          LN(NULLIF(market_value,0)) AS style_ln_mv_total,
          LN(NULLIF(circulated_market_value,0)) AS style_ln_mv_float,
          1 / NULLIF(pb_ratio,0) AS style_bp,
          1 / NULLIF(pe_ratio_ttm,0) AS style_ep_ttm,
          1 / NULLIF(f_sp,0) AS style_sp_ttm,
          1 / NULLIF(f_cfp,0) AS style_cfp_ttm,
          f_ev_ebitda AS style_ev_ebitda_ttm,
          f_tobin_q AS style_tobin_q,
          smb1 AS style_smb,
          hml1 AS style_hml,
          mkt_premium AS style_mkt_premium,
          beta20 AS style_beta_20,
          beta60 AS style_beta_60,
          beta120 AS style_beta_120,
          STDDEV_POP(ret_1d - beta20*mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS style_idio_vol_20,
          STDDEV_POP(ret_1d - beta60*mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS style_idio_vol_60,
          SUM(ret_1d - beta20*mkt_premium) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS style_residual_ret_20,
          COALESCE(PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY (1/NULLIF(pb_ratio,0))),0)
            + COALESCE(PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY (1/NULLIF(pe_ratio_ttm,0))),0)
            + COALESCE(PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY (1/NULLIF(f_cfp,0))),0) AS style_valuation_composite,
          PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY LN(NULLIF(market_value,0))) AS style_size_percentile,
          PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY (COALESCE(1/NULLIF(pb_ratio,0),0)+COALESCE(1/NULLIF(pe_ratio_ttm,0),0)+COALESCE(1/NULLIF(f_cfp,0),0))) AS style_value_percentile,
          ind_ret_1d, ind_ret_5d, ind_ret_10d, ind_ret_20d,
          ind_vol_20d AS ind_vol_20, ind_tover_20d AS ind_turnover_20, ind_amt_20d AS ind_amount_20,
          (close_price / NULLIF(lag_close_20,0) - 1) - ind_ret_20d AS ind_strength_20,
          (close_price / NULLIF(lag_close_60,0) - 1) - ind_ret_60d AS ind_strength_60,
          ind_disp AS ind_dispersion_20,
          ind_up_breadth AS ind_up_breadth_20,
          ind_down_breadth AS ind_down_breadth_20,
          volume / NULLIF(ind_vol_1d,0) AS ind_relative_volume_20,
          std20 / NULLIF(ind_vol_20d,0) AS ind_relative_volatility_20,
          (B_Amount - S_Amount) - ind_flow_20d AS ind_relative_flow_20,
          PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY ind_ret_20d) AS ind_momentum_rank_20,
          PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY ind_avg_bp) AS ind_value_rank,
          PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY ind_avg_mv) AS ind_size_rank,
          HASH(indcd) AS ind_code_l1,
          HASH(indcd || '_l2') AS ind_code_l2,
          Qsp_equal AS micro_qsp_equal, Esp_equal AS micro_esp_equal, AQsp_equal AS micro_aqsp_equal,
          Qsp_time AS micro_qsp_time, Esp_time AS micro_esp_time, Qsp_Volume AS micro_qsp_volume,
          Esp_Volume AS micro_esp_volume, Qsp_Amount AS micro_qsp_amount, Esp_Amount AS micro_esp_amount,
          Esp_equal AS micro_effective_spread, Qsp_equal AS micro_quoted_spread,
          STDDEV_POP(Esp_equal) OVER (PARTITION BY symbol ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS micro_spread_vol_20,
          (B_Volume - S_Volume) / NULLIF(B_Volume + S_Volume,0) AS micro_imbalance_volume,
          (B_Amount - S_Amount) / NULLIF(B_Amount + S_Amount,0) AS micro_imbalance_amount,
          (B_Num - S_Num) / NULLIF(B_Num + S_Num,0) AS micro_imbalance_count,
          (B_Amount_L - S_Amount_L) / NULLIF(B_Amount_L + S_Amount_L,0) AS micro_imbalance_large,
          (B_Amount_M - S_Amount_M) / NULLIF(B_Amount_M + S_Amount_M,0) AS micro_imbalance_medium,
          (B_Amount_S - S_Amount_S) / NULLIF(B_Amount_S + S_Amount_S,0) AS micro_imbalance_small,
          is_jump AS micro_jump_flag,
          (Esp_equal - mean_esp60) / NULLIF(std_esp60,0)
            + (vpin - mean_vpin60) / NULLIF(std_vpin60,0)
            + ((B_Amount - S_Amount) / NULLIF(B_Amount + S_Amount,0) - mean_imb60) / NULLIF(std_imb60,0) AS micro_pressure_score
        FROM calc4
      )
    )
    SELECT * FROM final_calc
    """
    con.execute(sql)

    if args.sample_limit > 0:
        con.execute(f"CREATE OR REPLACE TEMP TABLE feature_snapshot AS SELECT * FROM feature_snapshot_raw LIMIT {int(args.sample_limit)}")
    else:
        con.execute("CREATE OR REPLACE TEMP TABLE feature_snapshot AS SELECT * FROM feature_snapshot_raw")

    cols = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='feature_snapshot'").fetchall()}
    for k in feature_keys:
        if k not in cols:
            con.execute(f'ALTER TABLE feature_snapshot ADD COLUMN "{k}" DOUBLE')

    select_cols = ["symbol", "trade_date", *feature_keys]
    quoted = ", ".join(f'"{c}"' for c in select_cols)
    con.execute(f"CREATE OR REPLACE TEMP TABLE feature_snapshot_ordered AS SELECT {quoted} FROM feature_snapshot")

    con.execute(f"COPY feature_snapshot_ordered TO '{out_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    row_cnt = con.execute("SELECT COUNT(*) FROM feature_snapshot_ordered").fetchone()[0]
    null_stats = {}
    for k in feature_keys:
        v = con.execute(
            f'SELECT SUM(CASE WHEN "{k}" IS NULL THEN 1 ELSE 0 END)*1.0/NULLIF(COUNT(*),0) FROM feature_snapshot_ordered'
        ).fetchone()[0]
        null_stats[k] = float(v) if v is not None else 1.0

    fully_missing = [k for k, v in null_stats.items() if v >= 0.999999]
    report: dict[str, Any] = {
        "year": args.year,
        "rows": int(row_cnt),
        "feature_count": len(feature_keys),
        "fully_missing_feature_count": len(fully_missing),
        "fully_missing_features": fully_missing,
        "output_parquet": out_parquet.as_posix(),
        "sample_limit": args.sample_limit,
    }
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
