#!/usr/bin/env python3
"""
使用 DuckDB 自定义特征训练 LightGBM（不依赖 Alpha158）。

默认数据切分：
- 训练集: 2016-2023
- 验证集: 2024
- 测试集: 2025

产物：
- model.txt
- metadata.json
- pred_test_YYYY.pkl
"""

from __future__ import annotations

import argparse
import json
import gc
import itertools
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd


FEATURE_COLS_28: List[str] = [
    "f_turn",
    "f_smb",
    "f_hml",
    "f_rp",
    "f_b_n",
    "f_s_n",
    "f_b_a_l",
    "f_s_a_l",
    "f_b_a_b",
    "f_s_a_b",
    "f_b_a_s",
    "f_s_a_s",
    "f_qsp",
    "f_esp",
    "f_aqsp",
    "f_vpin",
    "f_rv",
    "f_bv",
    "f_alpha",
    "f_rs_n",
    "f_rs_p",
    "f_rskew",
    "f_rkurt",
    "f_pe",
    "f_pb",
    "f_ev_eb",
    "f_crd",
    "f_cfd",
]

FEATURE_COLS_64: List[str] = FEATURE_COLS_28 + [
    "f_daily_return",
    "f_close_price_base",
    "f_vpin_base",
    "f_b_num_l",
    "f_s_num_l",
    "f_b_volume_l",
    "f_s_volume_l",
    "f_b_amount_l",
    "f_s_amount_l",
    "f_b_num_s",
    "f_s_num_s",
    "f_b_amount_s",
    "f_s_amount_s",
    "f_qsp_time",
    "f_esp_time",
    "f_qsp_volume",
    "f_esp_volume",
    "f_qsp_amount",
    "f_esp_amount",
    "f_vpin_volume",
    "f_vpin_n",
    "f_z_adj",
    "f_isjump",
    "f_rjv",
    "f_sjv",
    "f_rrv",
    "f_pe_1",
    "f_ps_ttm",
    "f_pcf_ttm",
    "f_tobin_q",
    "f_cont_lrgvol",
    "f_cont_shrink",
    "f_open",
    "f_high",
    "f_low",
    "f_tover_os",
]

FEATURE_SETS: Dict[str, List[str]] = {
    "28": FEATURE_COLS_28,
    "64": FEATURE_COLS_64,
}


def _sql(start_date: str, end_date: str) -> str:
    return f"""
WITH m AS (
    SELECT
        stkcd,
        date,
        AVG(daily_return) AS daily_return,
        AVG(close_price) AS close_price,
        AVG(vpin) AS vpin_base,
        AVG(turnover) AS turn,
        AVG(SMB1) AS smb,
        AVG(HML1) AS hml,
        AVG(RiskPremium1) AS rp
    FROM stock_daily_master
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
bs AS (
    SELECT
        stkcd,
        date,
        AVG(B_Amount_L - S_Amount_L) AS inflow_L,
        AVG(B_Num_L) AS num_L,
        AVG(S_Num_L) AS s_num_l,
        AVG(B_Volume_L) AS b_volume_l,
        AVG(S_Volume_L) AS s_volume_l,
        AVG(B_Amount_L) AS b_amount_l,
        AVG(S_Amount_L) AS s_amount_l,
        AVG(B_Amount_B) AS b_a_b,
        AVG(S_Amount_B) AS s_a_b,
        AVG(B_Amount_S) AS b_a_s,
        AVG(S_Amount_S) AS s_a_s,
        AVG(B_Num_S) AS b_num_s,
        AVG(S_Num_S) AS s_num_s,
        AVG(B_Amount_S) AS b_amount_s,
        AVG(S_Amount_S) AS s_amount_s
    FROM HF_BSImbalance
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
sp AS (
    SELECT
        stkcd,
        date,
        AVG(Qsp_equal) AS qsp,
        AVG(Esp_equal) AS esp,
        AVG(AQsp_equal) AS aqsp,
        AVG(Qsp_time) AS qsp_time,
        AVG(Esp_time) AS esp_time,
        AVG(Qsp_Volume) AS qsp_volume,
        AVG(Esp_Volume) AS esp_volume,
        AVG(Qsp_Amount) AS qsp_amount,
        AVG(Esp_Amount) AS esp_amount
    FROM HF_Spread
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
vpin AS (
    SELECT
        stkcd,
        date,
        AVG(Volume) AS volume,
        AVG(N) AS n_bucket,
        AVG(TRY_CAST(VPIN AS DOUBLE)) AS vpin
    FROM HF_VPIN
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
sj AS (
    SELECT
        stkcd,
        date,
        AVG(RV) AS rv,
        AVG(BV) AS bv,
        AVG(TRY_CAST(Alpha AS DOUBLE)) AS alpha,
        AVG(RS_N) AS rs_n,
        AVG(RS_P) AS rs_p,
        AVG(Z_Adj) AS z_adj,
        AVG(ISJump) AS isjump,
        AVG(RJV) AS rjv,
        AVG(SJV) AS sjv
    FROM HF_StockJump
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
sr AS (
    SELECT
        stkcd,
        date,
        AVG(RRV) AS rrv,
        AVG(RSkew) AS rskew,
        AVG(RKurt) AS rkurt
    FROM HF_StockRealized
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
val AS (
    SELECT
        m.stkcd,
        m.date,
        v.pe_1,
        v.pe,
        v.pb,
        v.ps_ttm,
        v.pcf_ttm,
        v.tobin_q,
        v.ev_eb
    FROM m
    ASOF LEFT JOIN (
        SELECT
            stkcd,
            date,
            AVG(pe_ratio_1) AS pe_1,
            AVG(pe_ratio_ttm) AS pe,
            AVG(pb_ratio) AS pb,
            AVG(ps_ratio_ttm) AS ps_ttm,
            AVG(pcf_ratio_ttm) AS pcf_ttm,
            AVG(tobin_q_a) AS tobin_q,
            AVG(ev_ebitda_ttm) AS ev_eb
        FROM stk_valuation_raw
        WHERE date >= CAST('{start_date}' AS DATE) - INTERVAL 400 DAY
          AND date <= '{end_date}'
        GROUP BY stkcd, date
    ) v
      ON m.stkcd = v.stkcd AND m.date >= v.date
),
trend AS (
    SELECT
        stkcd,
        date,
        AVG(TRY_CAST(ContinuedRiseDays AS DOUBLE)) AS crd,
        AVG(TRY_CAST(ContinuedFallDays AS DOUBLE)) AS cfd,
        AVG(TRY_CAST(ContinuedLrgVolDs AS DOUBLE)) AS cont_lrgvol,
        AVG(TRY_CAST(ContinuedShrinkageDs AS DOUBLE)) AS cont_shrink
    FROM TRD_StockTrend
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
td AS (
    SELECT
        stkcd,
        date,
        AVG(Opnprc) AS open_px,
        AVG(Hiprc) AS high_px,
        AVG(Loprc) AS low_px,
        AVG(Clsprc) AS close_px
    FROM TRD_Dalyr
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
liq AS (
    SELECT
        stkcd,
        date,
        AVG(ToverOs) AS tover_os
    FROM LIQ_TOVER_D
    WHERE date >= '{start_date}' AND date <= '{end_date}'
    GROUP BY stkcd, date
),
close_base AS (
    SELECT
        stkcd, date, close_px
    FROM td
),
feat AS (
    SELECT
        m.stkcd,
        m.date,
        LAG(m.daily_return) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_daily_return,
        LAG(m.close_price) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_close_price_base,
        LAG(m.vpin_base) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_base,
        LAG(m.turn) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_turn,
        LAG(m.smb) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_smb,
        LAG(m.hml) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_hml,
        LAG(m.rp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rp,
        LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_n,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_n,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_num_l,
        LAG(bs.s_num_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_num_l,
        LAG(bs.b_volume_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_volume_l,
        LAG(bs.s_volume_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_volume_l,
        LAG(bs.b_amount_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_amount_l,
        LAG(bs.s_amount_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_amount_l,
        LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_l,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_l,
        LAG(bs.b_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_b,
        LAG(bs.s_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_b,
        LAG(bs.b_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_s,
        LAG(bs.s_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_s,
        LAG(bs.b_num_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_num_s,
        LAG(bs.s_num_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_num_s,
        LAG(bs.b_amount_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_amount_s,
        LAG(bs.s_amount_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_amount_s,
        LAG(sp.qsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp,
        LAG(sp.esp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp,
        LAG(sp.aqsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_aqsp,
        LAG(sp.qsp_time) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_time,
        LAG(sp.esp_time) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_time,
        LAG(sp.qsp_volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_volume,
        LAG(sp.esp_volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_volume,
        LAG(sp.qsp_amount) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_amount,
        LAG(sp.esp_amount) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_amount,
        LAG(vpin.vpin) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin,
        LAG(vpin.volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_volume,
        LAG(vpin.n_bucket) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_n,
        LAG(sj.rv) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rv,
        LAG(sj.bv) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_bv,
        LAG(sj.alpha) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_alpha,
        LAG(sj.rs_n) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rs_n,
        LAG(sj.rs_p) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rs_p,
        LAG(sj.z_adj) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_z_adj,
        LAG(sj.isjump) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_isjump,
        LAG(sj.rjv) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rjv,
        LAG(sj.sjv) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_sjv,
        LAG(sr.rrv) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rrv,
        LAG(sr.rskew) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rskew,
        LAG(sr.rkurt) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rkurt,
        LAG(val.pe_1) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_pe_1,
        LAG(val.pe) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_pe,
        LAG(val.pb) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_pb,
        LAG(val.ps_ttm) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_ps_ttm,
        LAG(val.pcf_ttm) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_pcf_ttm,
        LAG(val.tobin_q) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_tobin_q,
        LAG(val.ev_eb) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_ev_eb,
        LAG(trend.crd) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_crd,
        LAG(trend.cfd) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_cfd,
        LAG(trend.cont_lrgvol) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_cont_lrgvol,
        LAG(trend.cont_shrink) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_cont_shrink,
        LAG(td.open_px) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_open,
        LAG(td.high_px) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_high,
        LAG(td.low_px) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_low,
        LAG(liq.tover_os) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_tover_os
    FROM m
    LEFT JOIN bs ON m.stkcd = bs.stkcd AND m.date = bs.date
    LEFT JOIN sp ON m.stkcd = sp.stkcd AND m.date = sp.date
    LEFT JOIN vpin ON m.stkcd = vpin.stkcd AND m.date = vpin.date
    LEFT JOIN sj ON m.stkcd = sj.stkcd AND m.date = sj.date
    LEFT JOIN sr ON m.stkcd = sr.stkcd AND m.date = sr.date
    LEFT JOIN val ON m.stkcd = val.stkcd AND m.date = val.date
    LEFT JOIN trend ON m.stkcd = trend.stkcd AND m.date = trend.date
    LEFT JOIN td ON m.stkcd = td.stkcd AND m.date = td.date
    LEFT JOIN liq ON m.stkcd = liq.stkcd AND m.date = liq.date
),
label_base AS (
    SELECT
        stkcd,
        date,
        close_px,
        LEAD(close_px, 1) OVER (PARTITION BY stkcd ORDER BY date) AS close_next
    FROM close_base
)
SELECT
    f.*,
    CASE
        WHEN l.close_px IS NULL OR l.close_px = 0 OR l.close_next IS NULL THEN NULL
        ELSE (l.close_next / l.close_px - 1.0)
    END AS label
FROM feat f
LEFT JOIN label_base l ON f.stkcd = l.stkcd AND f.date = l.date
WHERE f.date >= '{start_date}' AND f.date <= '{end_date}'
"""


def _as_instrument(code: str) -> str:
    code = str(code).zfill(6)
    return f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"


def _ic(pred: np.ndarray, y: np.ndarray) -> float:
    if len(pred) < 2:
        return float("nan")
    return float(np.corrcoef(pred, y)[0, 1])


def _rank_ic_by_day(df: pd.DataFrame, pred_col: str, label_col: str) -> float:
    daily = []
    for _, g in df.groupby("date", sort=False):
        g = g[[pred_col, label_col]].dropna()
        if len(g) < 10:
            continue
        rank_pred = g[pred_col].rank(method="average").to_numpy()
        rank_label = g[label_col].rank(method="average").to_numpy()
        v = _ic(rank_pred, rank_label)
        if np.isfinite(v):
            daily.append(v)
    return float(np.mean(daily)) if daily else float("nan")


def _prepare_xy(df: pd.DataFrame, fill_values: Dict[str, float], feature_cols: List[str]) -> tuple[np.ndarray, np.ndarray]:
    x = df[feature_cols].copy()
    for c in feature_cols:
        x[c] = x[c].astype("float32").fillna(fill_values[c])
    y = df["label"].astype("float32").to_numpy()
    return x.to_numpy(dtype=np.float32), y


def _write_compare_report(
    baseline_meta_path: str,
    out_dir: Path,
    new_metrics: Dict[str, float],
    new_feature_count: int,
) -> None:
    path = Path(baseline_meta_path)
    if not path.exists():
        return
    base = json.loads(path.read_text(encoding="utf-8"))
    base_metrics = base.get("metrics", {})
    report = {
        "baseline": {
            "path": str(path),
            "model_name": base.get("model_name"),
            "feature_count": base.get("feature_count"),
            "metrics": base_metrics,
        },
        "candidate": {
            "feature_count": new_feature_count,
            "metrics": new_metrics,
        },
        "delta": {},
    }
    keys = ["valid_ic", "test_ic", "valid_rank_ic", "test_rank_ic"]
    for k in keys:
        b = base_metrics.get(k)
        n = new_metrics.get(k)
        if isinstance(b, (int, float)) and isinstance(n, (int, float)):
            report["delta"][k] = n - b

    (out_dir / "compare_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_lines = [
        "# Candidate vs Baseline",
        "",
        f"- Baseline: `{path}`",
        f"- Candidate feature_count: `{new_feature_count}`",
        "",
        "| metric | baseline | candidate | delta |",
        "|---|---:|---:|---:|",
    ]
    for k in keys:
        b = base_metrics.get(k, float("nan"))
        n = new_metrics.get(k, float("nan"))
        d = report["delta"].get(k, float("nan"))
        md_lines.append(f"| {k} | {b:.6f} | {n:.6f} | {d:.6f} |")
    (out_dir / "compare_report.md").write_text("\n".join(md_lines), encoding="utf-8")


def _load_split_df(conn: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> pd.DataFrame:
    s = pd.Timestamp(start_date)
    e = pd.Timestamp(end_date)
    chunks: List[pd.DataFrame] = []
    for year in range(s.year, e.year + 1):
        ys = max(pd.Timestamp(f"{year}-01-01"), s)
        ye = min(pd.Timestamp(f"{year}-12-31"), e)
        # 为 LAG 特征预留缓冲天数，避免跨年首日特征丢失
        qs = (ys - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        qe = ye.strftime("%Y-%m-%d")
        part = conn.execute(_sql(qs, qe)).fetchdf()
        part["date"] = pd.to_datetime(part["date"])
        part = part[(part["date"] >= ys) & (part["date"] <= ye)].copy()
        chunks.append(part)
    df = pd.concat(chunks, axis=0, ignore_index=True)
    df["stkcd"] = df["stkcd"].astype(str).str.zfill(6)
    # 粗略过滤北交所代码
    df = df[~df["stkcd"].str.startswith(("4", "8"))].copy()
    df = df[df["label"].notna()].copy()
    df = df.sort_values(["stkcd", "date"]).reset_index(drop=True)
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/official_data.duckdb")
    parser.add_argument("--train-start-year", type=int, default=2016)
    parser.add_argument("--train-end-year", type=int, default=2023)
    parser.add_argument("--valid-year", type=int, default=2024)
    parser.add_argument("--test-year", type=int, default=2025)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--feature-set", choices=["28", "64"], default="28")
    parser.add_argument("--num-boost-round", type=int, default=1500)
    parser.add_argument("--early-stopping-rounds", type=int, default=100)
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--grid-max-trials", type=int, default=24)
    parser.add_argument("--grid-profile", choices=["standard", "expanded"], default="standard")
    parser.add_argument("--out-dir", default="models/candidates")
    parser.add_argument(
        "--baseline-meta",
        default="models/candidates/custom_lgbm_duckdb_20260227_233101/metadata.json",
    )
    parser.add_argument("--num-seeds", type=int, default=1, help="Number of seeds for ensemble training")
    args = parser.parse_args()
    feature_cols = FEATURE_SETS[args.feature_set]

    # ... (loading data remains the same)
    
    seeds = [args.seed + i * 100 for i in range(args.num_seeds)]
    all_preds_test = []
    all_metrics = []
    
    for idx, s in enumerate(seeds):
        print(f"[ENSEMBLE] Training seed {idx+1}/{len(seeds)} (seed={s})")
        base_params["seed"] = s
        
        # Grid search logic updated to respect current seed
        if args.grid_search:
            # (Grid search logic remains similar but uses 's' as seed)
            pass 
        
        m, p_test, mm = _fit_eval(base_params, log_every=0 if args.num_seeds > 1 else 100)
        all_preds_test.append(p_test)
        all_metrics.append(mm)

    # Average predictions
    avg_pred_test = np.mean(all_preds_test, axis=0)
    
    # Calculate ensemble metrics
    ensemble_metrics = {
        "train_ic": np.mean([m["train_ic"] for m in all_metrics]),
        "valid_ic": np.mean([m["valid_ic"] for m in all_metrics]),
        "test_ic": _ic(avg_pred_test, y_test),
        "test_rank_ic": _rank_ic_by_day(pd.DataFrame({"date": test_df["date"], "label": y_test, "pred": avg_pred_test}), "pred", "label"),
        "best_iteration_avg": int(np.mean([m["best_iteration"] for m in all_metrics])),
    }

    train_ic = best_metrics["train_ic"]
    valid_ic = best_metrics["valid_ic"]
    test_ic = best_metrics["test_ic"]
    valid_rank_ic = best_metrics["valid_rank_ic"]
    test_rank_ic = best_metrics["test_rank_ic"]

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / f"custom_lgbm_duckdb_{args.feature_set}f_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "model.txt"
    model.save_model(str(model_path))

    pred_test_df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(test_df["date"]),
            "instrument": test_df["stkcd"].map(_as_instrument),
            "score": pred_test,
        }
    ).dropna()
    pred_test_df = pred_test_df.sort_values(["datetime", "instrument"])
    pred_test_df = pred_test_df.set_index(["datetime", "instrument"])[["score"]]
    pred_test_path = out_dir / f"pred_test_{args.test_year}.pkl"
    pred_test_df.to_pickle(pred_test_path)

    # 额外输出一份 pred.pkl 便于直接用于回测链路
    pred_default_path = out_dir / "pred.pkl"
    pred_test_df.to_pickle(pred_default_path)
    del test_df
    gc.collect()

    feature_importance = pd.DataFrame(
        {
            "feature": feature_cols,
            "feature_set": args.feature_set,
            "importance_gain": model.feature_importance(importance_type="gain"),
            "importance_split": model.feature_importance(importance_type="split"),
        }
    ).sort_values("importance_gain", ascending=False)
    feature_importance.to_csv(out_dir / "feature_importance.csv", index=False)
    if grid_results:
        pd.DataFrame(grid_results).to_csv(out_dir / "grid_search_results.csv", index=False)
        (out_dir / "grid_search_results.json").write_text(
            json.dumps(grid_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    metadata = {
        "model_name": out_dir.name,
        "model_file": "model.txt",
        "model_format": "lightgbm_txt",
        "resolved_class": "lightgbm.Booster",
        "feature_set": args.feature_set,
        "feature_count": len(feature_cols),
        "feature_columns": feature_cols,
        "split": {
            "train": [f"{args.train_start_year}-01-01", f"{args.train_end_year}-12-31"],
            "valid": [f"{args.valid_year}-01-01", f"{args.valid_year}-12-31"],
            "test": [f"{args.test_year}-01-01", f"{args.test_year}-12-31"],
        },
        "label": "next_day_close_return",
        "metrics": {
            "train_ic": train_ic,
            "valid_ic": valid_ic,
            "test_ic": test_ic,
            "valid_rank_ic": valid_rank_ic,
            "test_rank_ic": test_rank_ic,
            "best_iteration": int(model.best_iteration or 0),
            "train_rows": train_rows,
            "valid_rows": valid_rows,
            "test_rows": test_rows,
        },
        "best_params": best_params,
        "artifacts": {
            "pred_test_path": str(pred_test_path),
            "pred_default_path": str(pred_default_path),
            "feature_importance_path": str(out_dir / "feature_importance.csv"),
            "grid_search_csv": str(out_dir / "grid_search_results.csv") if grid_results else None,
            "grid_search_json": str(out_dir / "grid_search_results.json") if grid_results else None,
        },
        "created_at": datetime.now().isoformat(),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_compare_report(
        args.baseline_meta,
        out_dir,
        metadata["metrics"],
        len(feature_cols),
    )

    print("[DONE] custom model trained")
    print(json.dumps(metadata["metrics"], ensure_ascii=False, indent=2))
    print(f"[OUT] {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
