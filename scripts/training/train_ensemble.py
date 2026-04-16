#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path
import random
import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd

FEATURE_COLS_64: list[str] = [
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

def _sql(start_date: str, end_date: str) -> str:
    return f"""
WITH m AS (
    SELECT stkcd, date, AVG(daily_return) AS daily_return, AVG(close_price) AS close_price, 
           AVG(vpin) AS vpin_base, AVG(turnover) AS turn, AVG(SMB1) AS smb, AVG(HML1) AS hml, AVG(RiskPremium1) AS rp
    FROM stock_daily_master WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
bs AS (
    SELECT stkcd, date, AVG(B_Amount_L - S_Amount_L) AS inflow_L, AVG(B_Num_L) AS num_L, AVG(S_Num_L) AS s_num_l,
           AVG(B_Volume_L) AS b_volume_l, AVG(S_Volume_L) AS s_volume_l, AVG(B_Amount_L) AS b_amount_l, AVG(S_Amount_L) AS s_amount_l,
           AVG(B_Amount_B) AS b_a_b, AVG(S_Amount_B) AS s_a_b, AVG(B_Amount_S) AS b_a_s, AVG(S_Amount_S) AS s_a_s,
           AVG(B_Num_S) AS b_num_s, AVG(S_Num_S) AS s_num_s, AVG(B_Amount_S) AS b_amount_s, AVG(S_Amount_S) AS s_amount_s
    FROM HF_BSImbalance WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
sp AS (
    SELECT stkcd, date, AVG(Qsp_equal) AS qsp, AVG(Esp_equal) AS esp, AVG(AQsp_equal) AS aqsp, AVG(Qsp_time) AS qsp_time,
           AVG(Esp_time) AS esp_time, AVG(Qsp_Volume) AS qsp_volume, AVG(Esp_Volume) AS esp_volume, AVG(Qsp_Amount) AS qsp_amount, AVG(Esp_Amount) AS esp_amount
    FROM HF_Spread WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
vpin AS (
    SELECT stkcd, date, AVG(Volume) AS volume, AVG(N) AS n_bucket, AVG(TRY_CAST(VPIN AS DOUBLE)) AS vpin
    FROM HF_VPIN WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
sj AS (
    SELECT stkcd, date, AVG(RV) AS rv, AVG(BV) AS bv, AVG(TRY_CAST(Alpha AS DOUBLE)) AS alpha, AVG(RS_N) AS rs_n,
           AVG(RS_P) AS rs_p, AVG(Z_Adj) AS z_adj, AVG(ISJump) AS isjump, AVG(RJV) AS rjv, AVG(SJV) AS sjv
    FROM HF_StockJump WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
sr AS (
    SELECT stkcd, date, AVG(RRV) AS rrv, AVG(RSkew) AS rskew, AVG(RKurt) AS rkurt
    FROM HF_StockRealized WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
val AS (
    SELECT m.stkcd, m.date, v.pe_1, v.pe, v.pb, v.ps_ttm, v.pcf_ttm, v.tobin_q, v.ev_eb
    FROM m ASOF LEFT JOIN (
        SELECT stkcd, date, AVG(pe_ratio_1) AS pe_1, AVG(pe_ratio_ttm) AS pe, AVG(pb_ratio) AS pb,
               AVG(ps_ratio_ttm) AS ps_ttm, AVG(pcf_ratio_ttm) AS pcf_ttm, AVG(tobin_q_a) AS tobin_q, AVG(ev_ebitda_ttm) AS ev_eb
        FROM stk_valuation_raw WHERE date >= CAST('{start_date}' AS DATE) - INTERVAL 400 DAY AND date <= '{end_date}' GROUP BY stkcd, date
    ) v ON m.stkcd = v.stkcd AND m.date >= v.date
),
trend AS (
    SELECT stkcd, date, AVG(TRY_CAST(ContinuedRiseDays AS DOUBLE)) AS crd, AVG(TRY_CAST(ContinuedFallDays AS DOUBLE)) AS cfd,
           AVG(TRY_CAST(ContinuedLrgVolDs AS DOUBLE)) AS cont_lrgvol, AVG(TRY_CAST(ContinuedShrinkageDs AS DOUBLE)) AS cont_shrink
    FROM TRD_StockTrend WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
td AS (
    SELECT stkcd, date, AVG(Opnprc) AS open_px, AVG(Hiprc) AS high_px, AVG(Loprc) AS low_px, AVG(Clsprc) AS close_px
    FROM TRD_Dalyr WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
liq AS (
    SELECT stkcd, date, AVG(ToverOs) AS tover_os FROM LIQ_TOVER_D WHERE date >= '{start_date}' AND date <= '{end_date}' GROUP BY stkcd, date
),
feat AS (
    SELECT m.stkcd, m.date,
        LAG(m.daily_return) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_daily_return,
        LAG(m.close_price) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_close_price_base,
        LAG(m.vpin_base) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_base,
        LAG(m.turn) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_turn,
        LAG(m.smb) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_smb,
        LAG(m.hml) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_hml,
        LAG(m.rp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_rp,
        LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_n,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_n,
        LAG(bs.b_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_b,
        LAG(bs.s_a_b) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_b,
        LAG(bs.b_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_s,
        LAG(bs.s_a_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_s,
        LAG(sp.qsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp,
        LAG(sp.esp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp,
        LAG(sp.aqsp) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_aqsp,
        LAG(vpin.vpin) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin,
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
        LAG(liq.tover_os) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_tover_os,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_num_l,
        LAG(bs.s_num_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_num_l,
        LAG(bs.b_volume_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_volume_l,
        LAG(bs.s_volume_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_volume_l,
        LAG(bs.b_amount_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_amount_l,
        LAG(bs.s_amount_l) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_amount_l,
        LAG(bs.b_num_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_num_s,
        LAG(bs.s_num_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_num_s,
        LAG(bs.b_amount_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_amount_s,
        LAG(bs.s_amount_s) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_amount_s,
        LAG(sp.qsp_time) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_time,
        LAG(sp.esp_time) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_time,
        LAG(sp.qsp_volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_volume,
        LAG(sp.esp_volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_volume,
        LAG(sp.qsp_amount) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_qsp_amount,
        LAG(sp.esp_amount) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_esp_amount,
        LAG(vpin.volume) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_volume,
        LAG(vpin.n_bucket) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_vpin_n,
        LAG(sj.z_adj) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_z_adj,
        LAG(sj.isjump) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_isjump,
        LAG(bs.inflow_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_b_a_l,
        LAG(bs.num_L) OVER (PARTITION BY m.stkcd ORDER BY m.date) AS f_s_a_l
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
label_base AS ( SELECT stkcd, date, open_px, close_px, LEAD(close_px, 1) OVER (PARTITION BY stkcd ORDER BY date) AS close_next FROM td )
SELECT f.*, CASE WHEN l.close_px IS NULL OR l.close_px = 0 OR l.close_next IS NULL THEN NULL ELSE (l.close_next / l.close_px - 1.0) END AS label
FROM feat f LEFT JOIN label_base l ON f.stkcd = l.stkcd AND f.date = l.date
WHERE f.date >= '{start_date}' AND f.date <= '{end_date}'
"""

def _load_split_df(conn: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> pd.DataFrame:
    df = conn.execute(_sql(start_date, end_date)).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["label"].notna()].sort_values(["stkcd", "date"]).reset_index(drop=True)
    return df

def _rank_ic_by_day(df: pd.DataFrame, pred_col: str = "pred", label_col: str = "label") -> float:
    daily = []
    for _, g in df.groupby("date", sort=False):
        sub = g[[pred_col, label_col]].dropna()
        if len(sub) < 10:
            continue
        v = sub[pred_col].corr(sub[label_col], method="spearman")
        if pd.notna(v):
            daily.append(float(v))
    return float(np.mean(daily)) if daily else float("nan")

def _daily_rank_ic_series(df: pd.DataFrame, pred_col: str = "pred", label_col: str = "label") -> pd.Series:
    vals = []
    dates = []
    for d, g in df.groupby("date", sort=False):
        sub = g[[pred_col, label_col]].dropna()
        if len(sub) < 10:
            continue
        if sub[pred_col].nunique() <= 1 or sub[label_col].nunique() <= 1:
            continue
        v = sub[pred_col].corr(sub[label_col], method="spearman")
        if pd.notna(v):
            dates.append(d)
            vals.append(float(v))
    return pd.Series(vals, index=dates, dtype="float64")


def _build_grid(profile: str = "standard") -> list[dict]:
    if profile == "expanded":
        grid = {
            "num_leaves": [31, 63, 95],
            "max_depth": [8, 10, 12],
            "feature_fraction": [0.4, 0.5, 0.6, 0.7],
            "bagging_fraction": [0.5, 0.6, 0.7, 0.8],
            "min_data_in_leaf": [30, 60, 120],
            "lambda_l2": [0.0, 1.0, 3.0],
        }
    else:
        grid = {
            "num_leaves": [31, 63, 95],
            "max_depth": [8, 10, 12],
            "feature_fraction": [0.5, 0.6, 0.7],
            "bagging_fraction": [0.6, 0.7, 0.8],
            "min_data_in_leaf": [40, 80, 120],
            "lambda_l2": [0.0, 1.0],
        }

    keys = list(grid.keys())
    all_cfg = []
    from itertools import product

    for vals in product(*[grid[k] for k in keys]):
        all_cfg.append(dict(zip(keys, vals)))
    return all_cfg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="db/official_data.duckdb")
    parser.add_argument("--num-seeds", type=int, default=1)
    parser.add_argument("--num-boost-round", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--early-stopping-rounds", type=int, default=100)
    parser.add_argument("--grid-search", action="store_true")
    parser.add_argument("--grid-max-trials", type=int, default=32)
    parser.add_argument("--grid-profile", choices=["standard", "expanded"], default="standard")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default="models/candidates")
    args = parser.parse_args()
    
    conn = duckdb.connect(args.db, read_only=True)
    train_df = _load_split_df(conn, "2016-01-01", "2023-12-31")
    valid_df = _load_split_df(conn, "2024-01-01", "2024-12-31")
    test_df = _load_split_df(conn, "2025-01-01", "2025-12-31")
    conn.close()

    fill_v = {c: float(train_df[c].median()) for c in FEATURE_COLS_64}
    fill_v = {k: (0.0 if np.isnan(v) else v) for k, v in fill_v.items()}

    def prep(df):
        X = df[FEATURE_COLS_64].fillna(fill_v).astype("float32").to_numpy()
        return X, df["label"].astype("float32").to_numpy()

    x_train, y_train = prep(train_df)
    x_valid, y_valid = prep(valid_df)
    x_test, y_test = prep(test_df)
    
    dtrain = lgb.Dataset(x_train, label=y_train, feature_name=FEATURE_COLS_64)
    dvalid = lgb.Dataset(x_valid, label=y_valid, reference=dtrain)

    base_params = {
        "objective": "regression",
        "metric": "l2",
        "boosting_type": "gbdt",
        "feature_pre_filter": False,
        "learning_rate": args.learning_rate,
        "num_leaves": 63,
        "max_depth": 10,
        "feature_fraction": 0.5,
        "bagging_fraction": 0.6,
        "min_data_in_leaf": 60,
        "lambda_l2": 0.0,
        "verbosity": -1,
    }

    best_params = dict(base_params)
    grid_results = []
    if args.grid_search:
        candidates = _build_grid(args.grid_profile)
        rnd = random.Random(args.seed)
        if len(candidates) > args.grid_max_trials:
            candidates = rnd.sample(candidates, args.grid_max_trials)
        best_rank_ic = -1e18
        for i, cfg in enumerate(candidates, start=1):
            params = dict(base_params)
            params.update(cfg)
            params["seed"] = args.seed
            model_trial = lgb.train(
                params,
                dtrain,
                num_boost_round=args.num_boost_round,
                valid_sets=[dvalid],
                callbacks=[lgb.early_stopping(args.early_stopping_rounds, verbose=False)],
            )
            pred_valid = model_trial.predict(x_valid)
            valid_eval = valid_df[["date", "label"]].copy()
            valid_eval["pred"] = pred_valid
            rank_ic = _rank_ic_by_day(valid_eval)
            row = dict(cfg)
            row.update(
                {
                    "trial": i,
                    "valid_rank_ic": rank_ic,
                    "best_iteration": int(model_trial.best_iteration or 0),
                }
            )
            grid_results.append(row)
            print(
                f"[GRID] trial={i}/{len(candidates)} valid_rank_ic={rank_ic:.6f} best_iter={row['best_iteration']}"
            )
            if np.isfinite(rank_ic) and rank_ic > best_rank_ic:
                best_rank_ic = rank_ic
                best_params = dict(params)

    print("[BEST PARAMS]", json.dumps(best_params, ensure_ascii=False))

    all_preds = []
    models = []
    for i in range(args.num_seeds):
        seed = args.seed + i * 100
        print(f"[ENSEMBLE] Training seed {i+1}/{args.num_seeds} (seed={seed})")
        params = dict(best_params)
        params["seed"] = seed
        m = lgb.train(
            params,
            dtrain,
            num_boost_round=args.num_boost_round,
            valid_sets=[dvalid],
            callbacks=[lgb.early_stopping(args.early_stopping_rounds)],
        )
        all_preds.append(m.predict(x_test))
        models.append(m)

    avg_pred = np.mean(all_preds, axis=0)
    test_eval = test_df[["date", "label"]].copy()
    test_eval["pred"] = avg_pred

    daily_ic = _daily_rank_ic_series(test_eval, "pred", "label")
    rank_ic = float(daily_ic.mean()) if not daily_ic.empty else float("nan")
    std = float(daily_ic.std()) if not daily_ic.empty else float("nan")
    iric = float(rank_ic / std) if np.isfinite(std) and std != 0 else float("nan")
    res = {
        "rank_ic": rank_ic,
        "iric": iric,
        "learning_rate": args.learning_rate,
        "early_stopping_rounds": args.early_stopping_rounds,
        "best_iteration_avg": int(np.mean([m.best_iteration or 0 for m in models])),
    }
    print("--- ENSEMBLE RESULT ---")
    print(json.dumps(res, indent=2))

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out_dir) / f"ensemble_{args.num_seeds}s_{tag}"
    out.mkdir(parents=True, exist_ok=True)
    pred_df = pd.DataFrame(
        {
            "datetime": pd.to_datetime(test_df["date"]),
            "instrument": test_df["stkcd"].astype(str).str.zfill(6).map(
                lambda c: f"SH{c}" if c.startswith(("5", "6", "9")) else f"SZ{c}"
            ),
            "score": avg_pred,
        }
    ).dropna()
    pred_df = pred_df.sort_values(["datetime", "instrument"]).set_index(["datetime", "instrument"])[["score"]]
    pred_df.to_pickle(out / "pred_test_2025.pkl")
    pred_df.to_pickle(out / "pred.pkl")

    if grid_results:
        pd.DataFrame(grid_results).sort_values("valid_rank_ic", ascending=False).to_csv(
            out / "grid_search_results.csv", index=False
        )
    metadata = {
        "metrics": res,
        "best_params": best_params,
        "args": vars(args),
    }
    (out / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if models:
        models[0].save_model(str(out / "model.txt"))
    print(f"[OUT] {out}")

if __name__ == "__main__":
    main()
