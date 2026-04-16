#!/usr/bin/env python3
"""Train LightGBM preview model on 51D complete stocks.

Spec:
- Universe window: 2016-2025
- Split: train(2016-2023), valid(2024), test(2025)
- Exclude incomplete stocks (default from tmp/qlib_incomplete_stocks.tsv)
- Learning rate fixed at 0.01
- Early stopping enabled
- Outputs to models/model_preview
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import pickle
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "models" / "model_preview"
INCOMPLETE_LIST = ROOT / "tmp" / "qlib_incomplete_stocks.tsv"
FEATURES_DIR = ROOT / "db" / "qlib_data" / "features"

TRAIN_START = "2016-01-01"
TRAIN_END = "2023-12-31"
VALID_START = "2024-01-01"
VALID_END = "2024-12-31"
TEST_START = "2025-01-01"
TEST_END = "2025-12-31"
FULL_START = "2016-01-01"
FULL_END = "2025-12-31"

# qlib standard forward label used in many workflows
LABEL_EXPR = "Ref($close, -2) / Ref($close, -1) - 1"


@dataclass
class SplitData:
    x: pd.DataFrame
    y: pd.Series


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def init_qlib() -> None:
    import qlib

    provider_uri = os.getenv("QLIB_PROVIDER_URI", "db/qlib_data")
    region = os.getenv("QLIB_REGION", "cn")
    if not Path(provider_uri).is_absolute():
        provider_uri = str((ROOT / provider_uri).resolve())
    qlib.init(provider_uri=provider_uri, region=region, joblib_backend="threading")
    print(f"[INFO] qlib initialized: provider_uri={provider_uri}, region={region}")


def read_incomplete_symbols(path: Path) -> set[str]:
    bad = set()
    if not path.exists():
        return bad
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        symbol = line.split("\t", 1)[0].strip()
        if symbol:
            bad.add(symbol.lower())
            bad.add(symbol.upper())
    return bad


def get_feature_names_51d(features_dir: Path) -> List[str]:
    names = sorted({p.name for p in features_dir.glob("*/*.day.bin")})
    if len(names) < 51:
        raise RuntimeError(f"feature name pool too small: {len(names)}")
    return names


def to_exprs(feature_bins: List[str]) -> List[str]:
    exprs = []
    for f in feature_bins:
        base = f.replace(".day.bin", "")
        exprs.append(f"${base}")
    return exprs


def get_complete_universe() -> Tuple[List[str], List[str]]:
    from qlib.data import D

    all_inst = D.list_instruments(D.instruments("all"), as_list=True)
    bad = read_incomplete_symbols(INCOMPLETE_LIST)
    keep = [s for s in all_inst if str(s) not in bad and str(s).lower() not in bad]
    keep = sorted(set(map(str, keep)))
    excluded = sorted(set(map(str, all_inst)) - set(keep))
    print(f"[INFO] universe all={len(all_inst)}, keep={len(keep)}, excluded={len(excluded)}")
    return keep, excluded


def fetch_dataset(instruments: List[str], feature_exprs: List[str]) -> pd.DataFrame:
    from qlib.data import D

    exprs = feature_exprs + [LABEL_EXPR]
    cols = [e[1:] for e in feature_exprs] + ["label"]
    print(f"[INFO] fetching features: instruments={len(instruments)}, exprs={len(exprs)}")
    df = D.features(
        instruments,
        exprs,
        start_time=FULL_START,
        end_time=FULL_END,
    )
    if df is None or df.empty:
        raise RuntimeError("empty dataset from qlib")
    df.columns = cols
    return df


def sanitize_df(df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
    # drop rows without label, keep features with simple imputation
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["label"])
    x = df[feature_cols].copy()
    x = x.astype(np.float32)
    x = x.ffill().bfill().fillna(0.0)
    df[feature_cols] = x
    df["label"] = df["label"].astype(np.float32)
    return df


def split_by_date(df: pd.DataFrame, feature_cols: List[str]) -> Tuple[SplitData, SplitData, SplitData]:
    dt = pd.to_datetime(df.index.get_level_values("datetime"))
    train_mask = (dt >= pd.Timestamp(TRAIN_START)) & (dt <= pd.Timestamp(TRAIN_END))
    valid_mask = (dt >= pd.Timestamp(VALID_START)) & (dt <= pd.Timestamp(VALID_END))
    test_mask = (dt >= pd.Timestamp(TEST_START)) & (dt <= pd.Timestamp(TEST_END))

    def mk(mask: pd.Series) -> SplitData:
        part = df.loc[mask]
        return SplitData(x=part[feature_cols], y=part["label"])

    train = mk(train_mask)
    valid = mk(valid_mask)
    test = mk(test_mask)
    print(
        f"[INFO] split rows train/valid/test = "
        f"{len(train.y)}/{len(valid.y)}/{len(test.y)}"
    )
    return train, valid, test


def calc_ic_by_date(y_true: pd.Series, y_pred: np.ndarray, index: pd.MultiIndex) -> Dict[str, float]:
    tmp = pd.DataFrame(
        {
            "label": y_true.values,
            "pred": y_pred,
            "datetime": pd.to_datetime(index.get_level_values("datetime")),
        }
    )
    grouped = tmp.groupby("datetime", sort=True)
    ic_list = []
    ric_list = []
    for _, g in grouped:
        if len(g) < 5:
            continue
        ic = g["pred"].corr(g["label"], method="pearson")
        ric = g["pred"].corr(g["label"], method="spearman")
        if pd.notna(ic):
            ic_list.append(float(ic))
        if pd.notna(ric):
            ric_list.append(float(ric))

    def safe_mean_std(values: List[float]) -> Tuple[float, float]:
        if not values:
            return 0.0, 0.0
        arr = np.array(values, dtype=float)
        return float(arr.mean()), float(arr.std(ddof=1) if len(arr) > 1 else 0.0)

    ic_mean, ic_std = safe_mean_std(ic_list)
    ric_mean, ric_std = safe_mean_std(ric_list)
    return {
        "ic_mean": ic_mean,
        "ic_ir": (ic_mean / ic_std) if ic_std > 1e-12 else 0.0,
        "rank_ic_mean": ric_mean,
        "rank_ic_ir": (ric_mean / ric_std) if ric_std > 1e-12 else 0.0,
    }


def save_predictions(df_part: pd.DataFrame, preds: np.ndarray, out_path: Path) -> None:
    pred_df = pd.DataFrame({"score": preds.astype(np.float32)}, index=df_part.index)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_pickle(out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train preview LightGBM model on 51D features.")
    parser.add_argument("--grid-search", action="store_true", help="Enable grid search on key hyperparameters.")
    parser.add_argument("--grid-max-trials", type=int, default=24, help="Max grid trials when --grid-search is enabled.")
    parser.add_argument(
        "--score-metric",
        type=str,
        default="rank_ic_mean",
        choices=["rank_ic_mean", "ic_mean", "rank_ic_ir", "ic_ir"],
        help="Validation metric used to select best trial.",
    )
    parser.add_argument("--num-boost-round", type=int, default=5000, help="LightGBM max boost rounds.")
    parser.add_argument("--early-stopping-rounds", type=int, default=200, help="Early stopping rounds.")
    parser.add_argument("--learning-rate", type=float, default=0.01, help="Learning rate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for training and trial sampling.")
    return parser.parse_args()


def build_trial_candidates(base_params: Dict[str, Any], args: argparse.Namespace) -> List[Dict[str, Any]]:
    if not args.grid_search:
        return [dict(base_params)]

    grid = {
        "num_leaves": [63, 127, 255, 511],
        "min_data_in_leaf": [40, 80, 120],
        "feature_fraction": [0.8, 0.9, 1.0],
        "bagging_fraction": [0.8, 0.9, 1.0],
        "lambda_l2": [0.1, 1.0, 5.0],
    }
    keys = list(grid.keys())
    combos = []
    for values in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(base_params)
        for k, v in zip(keys, values):
            cfg[k] = v
        combos.append(cfg)

    rng = np.random.default_rng(args.seed)
    if args.grid_max_trials > 0 and len(combos) > args.grid_max_trials:
        idx = np.arange(len(combos))
        rng.shuffle(idx)
        combos = [combos[i] for i in idx[: args.grid_max_trials]]
    return combos


def extract_score(metric_dict: Dict[str, float], key: str) -> float:
    value = metric_dict.get(key)
    if value is None or not np.isfinite(value):
        return float("-inf")
    return float(value)


def train() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    init_qlib()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    feature_bins = get_feature_names_51d(FEATURES_DIR)
    feature_exprs = to_exprs(feature_bins)
    feature_cols = [f.replace(".day.bin", "") for f in feature_bins]
    print(f"[INFO] feature dims={len(feature_cols)}")

    keep, excluded = get_complete_universe()
    df = fetch_dataset(keep, feature_exprs)
    df = sanitize_df(df, feature_cols)
    train_s, valid_s, test_s = split_by_date(df, feature_cols)

    lgb_train = lgb.Dataset(train_s.x, label=train_s.y, feature_name=feature_cols)
    lgb_valid = lgb.Dataset(valid_s.x, label=valid_s.y, feature_name=feature_cols)

    base_params = {
        "objective": "regression",
        "metric": ["l2", "l1"],
        "learning_rate": float(args.learning_rate),
        "num_leaves": 255,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "min_data_in_leaf": 80,
        "lambda_l1": 0.0,
        "lambda_l2": 1.0,
        "verbosity": -1,
        "num_threads": max(1, (os.cpu_count() or 4) - 1),
        "seed": int(args.seed),
    }
    trial_params = build_trial_candidates(base_params, args)
    print(f"[INFO] training mode={'grid-search' if args.grid_search else 'single'}, trials={len(trial_params)}")

    best_trial: Dict[str, Any] | None = None
    best_booster: lgb.Booster | None = None
    trial_rows: List[Dict[str, Any]] = []

    for idx, params in enumerate(trial_params, start=1):
        print(
            f"[INFO] trial {idx}/{len(trial_params)}: "
            f"num_leaves={params['num_leaves']}, min_data_in_leaf={params['min_data_in_leaf']}, "
            f"feature_fraction={params['feature_fraction']}, bagging_fraction={params['bagging_fraction']}, "
            f"lambda_l2={params['lambda_l2']}"
        )
        booster = lgb.train(
            params=params,
            train_set=lgb_train,
            num_boost_round=int(args.num_boost_round),
            valid_sets=[lgb_train, lgb_valid],
            valid_names=["train", "valid"],
            callbacks=[
                lgb.early_stopping(stopping_rounds=int(args.early_stopping_rounds)),
                lgb.log_evaluation(period=200),
            ],
        )
        best_iter = booster.best_iteration or int(args.num_boost_round)
        valid_pred = booster.predict(valid_s.x, num_iteration=best_iter)
        valid_ic = calc_ic_by_date(valid_s.y, valid_pred, valid_s.x.index)
        score = extract_score(valid_ic, args.score_metric)

        row = {
            "trial": idx,
            "score_metric": args.score_metric,
            "score": score,
            "best_iteration": int(best_iter),
            "num_leaves": int(params["num_leaves"]),
            "min_data_in_leaf": int(params["min_data_in_leaf"]),
            "feature_fraction": float(params["feature_fraction"]),
            "bagging_fraction": float(params["bagging_fraction"]),
            "lambda_l2": float(params["lambda_l2"]),
            "learning_rate": float(params["learning_rate"]),
            "valid_ic_mean": float(valid_ic["ic_mean"]),
            "valid_ic_ir": float(valid_ic["ic_ir"]),
            "valid_rank_ic_mean": float(valid_ic["rank_ic_mean"]),
            "valid_rank_ic_ir": float(valid_ic["rank_ic_ir"]),
        }
        trial_rows.append(row)
        if best_trial is None or row["score"] > best_trial["score"]:
            best_trial = row
            best_booster = booster

    if best_trial is None or best_booster is None:
        raise RuntimeError("training failed: no successful trial")

    best_iter = int(best_trial["best_iteration"])
    print(
        f"[INFO] selected trial={best_trial['trial']}, {args.score_metric}={best_trial['score']:.6f}, "
        f"best_iteration={best_iter}"
    )
    valid_pred = best_booster.predict(valid_s.x, num_iteration=best_iter)
    test_pred = best_booster.predict(test_s.x, num_iteration=best_iter)
    valid_ic = calc_ic_by_date(valid_s.y, valid_pred, valid_s.x.index)
    test_ic = calc_ic_by_date(test_s.y, test_pred, test_s.x.index)

    # Save model
    best_booster.save_model(str(OUT_DIR / "model.txt"), num_iteration=best_iter)
    with open(OUT_DIR / "model.pkl", "wb") as f:
        pickle.dump(best_booster, f)

    # Save predictions
    valid_df = df.loc[
        (pd.to_datetime(df.index.get_level_values("datetime")) >= pd.Timestamp(VALID_START))
        & (pd.to_datetime(df.index.get_level_values("datetime")) <= pd.Timestamp(VALID_END))
    ]
    test_df = df.loc[
        (pd.to_datetime(df.index.get_level_values("datetime")) >= pd.Timestamp(TEST_START))
        & (pd.to_datetime(df.index.get_level_values("datetime")) <= pd.Timestamp(TEST_END))
    ]
    save_predictions(valid_df, valid_pred, OUT_DIR / "pred_2024.pkl")
    save_predictions(test_df, test_pred, OUT_DIR / "pred_2025.pkl")
    pred_all = pd.concat(
        [
            pd.DataFrame({"score": valid_pred.astype(np.float32)}, index=valid_df.index),
            pd.DataFrame({"score": test_pred.astype(np.float32)}, index=test_df.index),
        ]
    ).sort_index()
    pred_all.to_pickle(OUT_DIR / "pred.pkl")

    selected_params = dict(base_params)
    selected_params.update(
        {
            "num_leaves": best_trial["num_leaves"],
            "min_data_in_leaf": best_trial["min_data_in_leaf"],
            "feature_fraction": best_trial["feature_fraction"],
            "bagging_fraction": best_trial["bagging_fraction"],
            "lambda_l2": best_trial["lambda_l2"],
        }
    )

    metadata = {
        "model_name": "model_preview_lgbm_51d",
        "model_file": "model.txt",
        "model_format": "lightgbm_txt_pickle",
        "feature_count": len(feature_cols),
        "feature_files": feature_bins,
        "label_expr": LABEL_EXPR,
        "split": {
            "train": [TRAIN_START, TRAIN_END],
            "valid": [VALID_START, VALID_END],
            "test": [TEST_START, TEST_END],
        },
        "universe": {
            "total_keep": len(keep),
            "excluded_count": len(excluded),
            "excluded_list_file": str(INCOMPLETE_LIST.relative_to(ROOT)),
        },
        "training_mode": "grid_search" if args.grid_search else "single",
        "score_metric": args.score_metric,
        "lightgbm_params": selected_params,
        "best_iteration": int(best_iter),
        "best_trial": best_trial,
        "metrics": {
            "valid": valid_ic,
            "test": test_ic,
        },
        "generated_at": datetime.now().isoformat(),
    }
    (OUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "feature_schema.json").write_text(
        json.dumps(
            {
                "feature_count": len(feature_cols),
                "features": feature_cols,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if trial_rows:
        pd.DataFrame(trial_rows).sort_values("score", ascending=False).to_csv(
            OUT_DIR / "grid_search_results.csv", index=False
        )

    report_lines = [
        "# model_preview 训练报告",
        "",
        f"- 训练时间: {datetime.now().isoformat()}",
        f"- 股票池: {len(keep)}（排除 {len(excluded)} 只不完整股票）",
        f"- 特征维度: {len(feature_cols)}",
        f"- 训练模式: {'网格搜索' if args.grid_search else '单组参数'}",
        f"- 评分指标: {args.score_metric}",
        f"- 最佳迭代: {best_iter}",
        f"- 最优参数: num_leaves={best_trial['num_leaves']}, min_data_in_leaf={best_trial['min_data_in_leaf']}, "
        f"feature_fraction={best_trial['feature_fraction']}, bagging_fraction={best_trial['bagging_fraction']}, "
        f"lambda_l2={best_trial['lambda_l2']}",
        "",
        "## 验证集 (2024)",
        f"- IC: {valid_ic['ic_mean']:.6f}, ICIR: {valid_ic['ic_ir']:.6f}",
        f"- RankIC: {valid_ic['rank_ic_mean']:.6f}, RankICIR: {valid_ic['rank_ic_ir']:.6f}",
        "",
        "## 测试集 (2025)",
        f"- IC: {test_ic['ic_mean']:.6f}, ICIR: {test_ic['ic_ir']:.6f}",
        f"- RankIC: {test_ic['rank_ic_mean']:.6f}, RankICIR: {test_ic['rank_ic_ir']:.6f}",
        "",
    ]
    if args.grid_search:
        report_lines.extend(
            [
                "## 网格搜索",
                f"- 试验数量: {len(trial_rows)}",
                f"- 结果文件: {(OUT_DIR / 'grid_search_results.csv').relative_to(ROOT)}",
                "",
            ]
        )
    (OUT_DIR / "train_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(f"[DONE] artifacts saved to: {OUT_DIR}")


if __name__ == "__main__":
    train()
