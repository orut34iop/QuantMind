#!/usr/bin/env python3
"""
QuantMind 通用模型推理脚本
===========================
完全由 metadata.json 驱动，无需手动指定特征列表或模型参数。

支持三种模式：
  daily   - 推理指定单日（或最新日）的全市场预测分
  range   - 批量推理日期区间（回填历史预测）
  eval    - 计算 IC/RankIC 评估（需要实际标签）

用法：
  python scripts/run_inference.py daily   --model /app/models/production/model_qlib
  python scripts/run_inference.py range   --model /app/models/production/model_qlib \
                                          --start 2025-01-01 --end 2025-12-31
  python scripts/run_inference.py eval    --model /app/models/production/model_qlib \
                                          --start 2025-01-01 --end 2025-12-31
  python scripts/run_inference.py daily   --model /app/models/users/default/00000001/mdl_train_xxx
"""

import argparse
import json
import logging
import os
import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ── 路径 ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR     = PROJECT_ROOT / "db" / "feature_snapshots"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "predictions"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("Inference")


# ═══════════════════════════════════════════════════════════════════════════
# 1. 元数据加载
# ═══════════════════════════════════════════════════════════════════════════

def load_metadata(model_dir: Path) -> dict:
    """从 metadata.json 动态加载所有推理所需配置。"""
    meta_path = model_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.json not found in {model_dir}")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    logger.info("=== 模型配置 ===")
    logger.info("  run_id          : %s", meta.get("run_id", "unknown"))
    logger.info("  model_name      : %s", meta.get("model_name", "unknown"))
    logger.info("  framework       : %s", meta.get("framework", "lightgbm"))
    logger.info("  target_horizon  : T+%s", meta.get("target_horizon_days", "?"))
    logger.info("  label_formula   : %s", meta.get("label_formula") or "(close[t+N]/close[t])-1")
    logger.info("  training_window : %s", meta.get("training_window") or
                f"{meta.get('train_start')} ~ {meta.get('train_end')}")
    logger.info("  split           : val %s~%s  test %s~%s",
                meta.get("val_start","?"), meta.get("val_end","?"),
                meta.get("test_start","?"), meta.get("test_end","?"))
    logger.info("  feature_count   : %s", meta.get("feature_count", len(meta.get("features",[]))))
    logger.info("  pred_coverage   : %s ~ %s",
                meta.get("pred_coverage_start","?"), meta.get("pred_coverage_end","?"))
    return meta


# ═══════════════════════════════════════════════════════════════════════════
# 2. 模型加载
# ═══════════════════════════════════════════════════════════════════════════

def load_model(model_dir: Path, meta: dict):
    """自动识别框架并加载模型。"""
    framework = meta.get("framework", "lightgbm").lower()
    model_file_name = meta.get("model_file", "model.lgb")
    model_path = model_dir / model_file_name

    # 候选文件查找
    if not model_path.exists():
        candidates = (
            list(model_dir.glob("*.lgb")) +
            list(model_dir.glob("*.txt")) +
            list(model_dir.glob("*.pkl"))
        )
        if not candidates:
            raise FileNotFoundError(f"No model file found in {model_dir}")
        model_path = candidates[0]
        logger.warning("模型文件不匹配，使用候选: %s", model_path.name)

    logger.info("加载模型: %s  [%s]", model_path.name, framework)

    if framework == "lightgbm":
        if model_path.suffix == ".pkl":
            with open(model_path, "rb") as f:
                return pickle.load(f)
        return lgb.Booster(model_file=str(model_path))
    else:
        raise ValueError(f"当前脚本不支持框架: {framework}，请扩展 load_model()")


# ═══════════════════════════════════════════════════════════════════════════
# 3. 数据加载与预处理（与训练流水线一致）
# ═══════════════════════════════════════════════════════════════════════════

def load_parquet_for_dates(start: str, end: str, data_dir: Path) -> pd.DataFrame:
    """按年加载涵盖 [start, end] 区间的 parquet 文件。"""
    start_dt = pd.to_datetime(start)
    end_dt   = pd.to_datetime(end)
    years = range(start_dt.year, end_dt.year + 1)

    chunks = []
    for year in years:
        p = data_dir / f"train_ready_{year}.parquet"
        if not p.exists():
            logger.warning("parquet 不存在: %s，跳过", p.name)
            continue
        df = pd.read_parquet(p, engine="pyarrow")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mask = (df["trade_date"] >= start_dt) & (df["trade_date"] <= end_dt)
        chunks.append(df[mask])
        logger.info("  加载 %s: %d 行", p.name, mask.sum())

    if not chunks:
        raise ValueError(f"[{start}, {end}] 区间内无可用数据")

    result = pd.concat(chunks, ignore_index=True)
    logger.info("合并后共 %d 行，%d 列", len(result), len(result.columns))
    return result


def resolve_label_col(df: pd.DataFrame, meta: dict) -> Optional[str]:
    """
    从 metadata 推断训练时用的 label 列名。
    优先级：target_column > 'label'（固定名） > mom_ret_{horizon}d
    """
    if meta.get("target_column") and meta["target_column"] in df.columns:
        return meta["target_column"]
    if "label" in df.columns:
        return "label"
    horizon = int(meta.get("target_horizon_days", 5))
    candidate = f"mom_ret_{horizon}d"
    return candidate if candidate in df.columns else None


def preprocess(df: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    按 metadata.json 中的 features/fill_values 预处理数据。
    返回 (X_df, meta_df)
    meta_df 包含 symbol/trade_date/label（如存在）
    """
    feature_cols = meta.get("feature_columns") or meta.get("features", [])
    fill_values  = meta.get("fill_values", {})

    # 检查缺失特征
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning("数据中缺少 %d 个特征，将用0填充: %s", len(missing), missing[:10])
        for c in missing:
            df[c] = 0.0

    # 提取特征矩阵
    X_df = df[feature_cols].copy()

    # 按 metadata 的 fill_values 填充（与训练一致）
    for col, val in fill_values.items():
        if col in X_df.columns:
            X_df[col] = X_df[col].fillna(val)
    # 剩余 NaN 填 0
    X_df = X_df.fillna(0.0)

    # 元信息列（自动识别 label 列）
    meta_cols = ["symbol", "trade_date"]
    label_col = resolve_label_col(df, meta)
    if label_col:
        meta_cols.append(label_col)
        logger.info("使用标签列: %s", label_col)
    meta_df = df[meta_cols].copy()

    logger.info("预处理完成: X shape=%s, feature_count=%d", X_df.shape, len(feature_cols))
    return X_df, meta_df


# ═══════════════════════════════════════════════════════════════════════════
# 4. 推理核心
# ═══════════════════════════════════════════════════════════════════════════

def predict(model, X_df: pd.DataFrame, meta: dict) -> pd.Series:
    """执行模型推理，返回 pd.Series（与 X_df 索引对齐）。"""
    framework = meta.get("framework", "lightgbm").lower()
    X = X_df.values.astype(np.float32)

    if framework == "lightgbm":
        best_iter = meta.get("best_iteration")
        scores = model.predict(X, num_iteration=best_iter)
    else:
        scores = model.predict(X)

    return pd.Series(scores, index=X_df.index, name="score")


# ═══════════════════════════════════════════════════════════════════════════
# 5. IC 评估
# ═══════════════════════════════════════════════════════════════════════════

def compute_ic(pred_df: pd.DataFrame, label_col: str) -> dict:
    """
    逐截面（每日）计算 IC/RankIC，返回汇总统计。
    pred_df 需含 trade_date / score / {label_col} 列。
    """
    records = []
    for date, grp in pred_df.groupby("trade_date"):
        g = grp[["score", label_col]].dropna()
        if len(g) < 20:
            continue
        ic      = g["score"].corr(g[label_col])
        rank_ic = spearmanr(g["score"], g[label_col]).statistic
        records.append({"date": date, "ic": ic, "rank_ic": rank_ic})

    if not records:
        logger.warning("IC 计算：有效截面数为0")
        return {}

    ic_df = pd.DataFrame(records).set_index("date")
    summary = {
        "ic_mean":       round(ic_df["ic"].mean(), 6),
        "ic_std":        round(ic_df["ic"].std(), 6),
        "icir":          round(ic_df["ic"].mean() / (ic_df["ic"].std() + 1e-9), 4),
        "rank_ic_mean":  round(ic_df["rank_ic"].mean(), 6),
        "rank_ic_std":   round(ic_df["rank_ic"].std(), 6),
        "rank_icir":     round(ic_df["rank_ic"].mean() / (ic_df["rank_ic"].std() + 1e-9), 4),
        "ic_positive_rate": round((ic_df["ic"] > 0).mean(), 4),
        "n_dates":       len(ic_df),
    }
    logger.info("── IC 评估结果 ────────────────────────")
    for k, v in summary.items():
        logger.info("  %-20s = %s", k, v)
    logger.info("────────────────────────────────────────")
    return summary


# ═══════════════════════════════════════════════════════════════════════════
# 6. 输出保存
# ═══════════════════════════════════════════════════════════════════════════

def save_predictions(pred_df: pd.DataFrame, output_path: Path, fmt: str = "parquet"):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "parquet":
        pred_df.to_parquet(output_path, index=False, engine="pyarrow", compression="snappy")
    elif fmt == "csv":
        pred_df.to_csv(output_path, index=False)
    elif fmt == "pkl":
        pred_df.to_pickle(output_path)
    logger.info("预测结果已保存: %s  (%d 行)", output_path, len(pred_df))


# ═══════════════════════════════════════════════════════════════════════════
# 7. 推理模式入口
# ═══════════════════════════════════════════════════════════════════════════

def mode_daily(model_dir: Path, target_date: Optional[str], output_fmt: str, data_dir: Path):
    """单日推理：对目标日期的所有股票打分。"""
    meta  = load_metadata(model_dir)
    model = load_model(model_dir, meta)

    # 确定目标日期
    if not target_date:
        # 用预测覆盖的最后一天
        target_date = meta.get("pred_coverage_end") or datetime.today().strftime("%Y-%m-%d")
    logger.info("推理日期: %s", target_date)

    raw      = load_parquet_for_dates(target_date, target_date, data_dir)
    X_df, meta_df = preprocess(raw, meta)
    scores   = predict(model, X_df, meta)

    pred_df = meta_df.copy()
    pred_df["score"] = scores.values
    pred_df = pred_df.sort_values("score", ascending=False)

    fname = f"pred_{target_date.replace('-','')}.{output_fmt}"
    save_predictions(pred_df, OUTPUT_DIR / fname, output_fmt)

    # 打印 Top20
    logger.info("── Top-20 预测 ─────────────────────────")
    print(pred_df[["symbol", "trade_date", "score"]].head(20).to_string(index=False))
    return pred_df


def mode_range(model_dir: Path, start: str, end: str, output_fmt: str, data_dir: Path):
    """区间批量推理：对 [start, end] 每天每支股票打分。"""
    meta  = load_metadata(model_dir)
    model = load_model(model_dir, meta)
    horizon = int(meta.get("target_horizon_days", 5))

    raw           = load_parquet_for_dates(start, end, data_dir)
    X_df, meta_df = preprocess(raw, meta)
    scores        = predict(model, X_df, meta)

    pred_df = meta_df.copy()
    pred_df["score"] = scores.values

    run_id = meta.get("run_id", "unknown")
    fname  = f"pred_range_{start}_{end}_{run_id[:16]}.{output_fmt}"
    save_predictions(pred_df, OUTPUT_DIR / fname, output_fmt)
    return pred_df


def mode_eval(model_dir: Path, start: str, end: str, data_dir: Path):
    """IC 评估：推理后与实际标签对比计算 IC。"""
    meta    = load_metadata(model_dir)
    model   = load_model(model_dir, meta)

    raw           = load_parquet_for_dates(start, end, data_dir)
    X_df, meta_df = preprocess(raw, meta)
    scores        = predict(model, X_df, meta)

    pred_df = meta_df.copy()
    pred_df["score"] = scores.values

    # 自动识别 label 列
    label_col = resolve_label_col(raw, meta)
    if not label_col or label_col not in pred_df.columns:
        logger.error("未找到标签列，无法计算IC。pred_df 列: %s", list(pred_df.columns))
        return pred_df

    # 过滤 NaN 标签
    pred_df = pred_df.dropna(subset=[label_col])

    summary = compute_ic(pred_df, label_col)

    # 与 metadata 中存储的训练期 IC 对比
    stored = meta.get("metrics", {})
    logger.info("── 与训练期 IC 对比 ────────────────────")
    for split, sk, ek in [
        ("train", "train_start", "train_end"),
        ("val",   "val_start",   "val_end"),
        ("test",  "test_start",  "test_end"),
    ]:
        ic_key = f"{split}_ic"
        if stored.get(ic_key):
            logger.info("  [metadata] %-8s IC = %.6f", split, stored[ic_key])
    logger.info("  [eval]    %s~%s  IC = %.6f  ICIR = %.4f",
                start, end, summary.get("ic_mean",0), summary.get("icir",0))

    return pred_df, summary


# ═══════════════════════════════════════════════════════════════════════════
# 8. CLI
# ═══════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="QuantMind 通用模型推理脚本（metadata.json 动态驱动）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("mode", choices=["daily", "range", "eval"],
                   help="推理模式: daily=单日 range=区间 eval=IC验证")
    p.add_argument("--model", "-m", type=str,
                   default="/app/models/production/model_qlib",
                   help="模型目录路径（含 metadata.json 和 model.lgb）")
    p.add_argument("--date", "-d", type=str, default=None,
                   help="[daily] 推理日期，格式 YYYY-MM-DD，默认为 pred_coverage_end")
    p.add_argument("--start", "-s", type=str, default=None,
                   help="[range/eval] 开始日期")
    p.add_argument("--end", "-e", type=str, default=None,
                   help="[range/eval] 结束日期")
    p.add_argument("--data-dir", type=str,
                   default=str(DATA_DIR),
                   help="训练数据 parquet 目录")
    p.add_argument("--output-fmt", type=str, default="parquet",
                   choices=["parquet", "csv", "pkl"],
                   help="输出格式（默认 parquet）")
    p.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR),
                   help="输出目录（默认 data/predictions）")
    return p.parse_args()


def main():
    args  = parse_args()
    mdir  = Path(args.model)
    ddir  = Path(args.data_dir)

    global OUTPUT_DIR
    OUTPUT_DIR = Path(args.output_dir)

    if not mdir.exists():
        logger.error("模型目录不存在: %s", mdir)
        sys.exit(1)

    logger.info("=" * 55)
    logger.info("QuantMind 推理脚本  mode=%s  model=%s", args.mode, mdir.name)
    logger.info("=" * 55)

    if args.mode == "daily":
        mode_daily(mdir, args.date, args.output_fmt, ddir)

    elif args.mode == "range":
        if not args.start or not args.end:
            logger.error("range 模式需要 --start 和 --end 参数")
            sys.exit(1)
        mode_range(mdir, args.start, args.end, args.output_fmt, ddir)

    elif args.mode == "eval":
        if not args.start or not args.end:
            logger.error("eval 模式需要 --start 和 --end 参数")
            sys.exit(1)
        mode_eval(mdir, args.start, args.end, ddir)


if __name__ == "__main__":
    main()
