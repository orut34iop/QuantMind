#!/usr/bin/env python3
"""逐年滚动生成线上可用预测文件（仅用当年可得信息）。"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import qlib
import yaml
from qlib.utils import init_instance_by_config

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_CONFIG = ROOT / "models/production/model_qlib/workflow_config.yaml"
DEFAULT_OUT = ROOT / "models/production/model_qlib/pred_rolling_2017_2025_online.pkl"
DEFAULT_META = (
    ROOT / "models/production/model_qlib/pred_rolling_2017_2025_online.meta.json"
)


def _year_segments(year: int) -> Dict[str, Tuple[str, str]]:
    # 2017 年无更早年份可用于标准 train/valid 分年切分，使用 2016 年内切分兜底。
    if year == 2017:
        return {
            "train": ("2016-01-01", "2016-09-30"),
            "valid": ("2016-10-01", "2016-12-30"),
            "test": ("2017-01-01", "2017-12-30"),
            "handler_end": ("2017-12-30", "2017-12-30"),
        }
    return {
        "train": ("2016-01-01", f"{year - 2}-12-31"),
        "valid": (f"{year - 1}-01-01", f"{year - 1}-12-31"),
        "test": (f"{year}-01-01", f"{year}-12-30"),
        "handler_end": (f"{year}-12-30", f"{year}-12-30"),
    }


def _build_task_cfg(base_cfg: dict, year: int) -> dict:
    cfg = copy.deepcopy(base_cfg)
    seg = _year_segments(year)

    handler_kwargs = cfg["task"]["dataset"]["kwargs"]["handler"]["kwargs"]
    handler_kwargs["end_time"] = seg["handler_end"][0]
    segments = cfg["task"]["dataset"]["kwargs"]["segments"]
    segments["train"] = list(seg["train"])
    segments["valid"] = list(seg["valid"])
    segments["test"] = list(seg["test"])

    # 关键防泄漏：归一化处理器只能用 year-1 及之前数据拟合分布
    infer_processors = handler_kwargs.get("infer_processors", [])
    fit_end = f"{year - 1}-12-31" if year > 2017 else "2016-12-30"
    for proc in infer_processors:
        if isinstance(proc, dict) and proc.get("class") == "RobustZScoreNorm":
            kwargs = proc.setdefault("kwargs", {})
            kwargs["fit_end_time"] = fit_end

    return cfg


def _normalize_pred(pred: pd.DataFrame | pd.Series) -> pd.DataFrame:
    if isinstance(pred, pd.Series):
        out = pred.to_frame("score")
    else:
        if "score" in pred.columns:
            out = pred[["score"]]
        else:
            out = pred.iloc[:, 0].to_frame("score")
    out = out.dropna()
    if isinstance(out.index, pd.MultiIndex) and "instrument" in out.index.names:
        inst = out.index.get_level_values("instrument").astype(str).str.upper()
        out = out.loc[~inst.str.startswith("BJ")]
    return out.sort_index()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--meta", type=str, default=str(DEFAULT_META))
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must <= end-year")

    workflow = yaml.safe_load(WORKFLOW_CONFIG.read_text(encoding="utf-8"))
    qlib.init(
        provider_uri="db/qlib_data", region="cn", kernels=1, joblib_backend="threading"
    )

    all_preds = []
    year_stats: Dict[str, dict] = {}

    for year in range(args.start_year, args.end_year + 1):
        cfg = _build_task_cfg(workflow, year)
        task_cfg = cfg["task"]
        model = init_instance_by_config(task_cfg["model"])
        dataset = init_instance_by_config(task_cfg["dataset"])

        print(f"[RUN] rolling year={year} fit(train<=year-1)")
        model.fit(dataset)
        pred = model.predict(dataset, segment="test")
        pred_df = _normalize_pred(pred)
        all_preds.append(pred_df)

        year_stats[str(year)] = {
            "rows": int(len(pred_df)),
            "trading_days": (
                int(pred_df.index.get_level_values("datetime").nunique())
                if len(pred_df)
                else 0
            ),
            "instruments": (
                int(pred_df.index.get_level_values("instrument").nunique())
                if len(pred_df)
                else 0
            ),
            "segments": cfg["task"]["dataset"]["kwargs"]["segments"],
        }
        print(
            f"[DONE] {year}: rows={year_stats[str(year)]['rows']} "
            f"days={year_stats[str(year)]['trading_days']} instruments={year_stats[str(year)]['instruments']}"
        )

    pred_all = pd.concat(all_preds, axis=0).sort_index()
    pred_all = pred_all[~pred_all.index.duplicated(keep="last")]

    out_path = Path(args.output)
    meta_path = Path(args.meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pred_all.to_pickle(out_path)

    meta = {
        "version": f"rolling_{args.start_year}_{args.end_year}_online",
        "created_at": datetime.now().isoformat(),
        "workflow_config": str(WORKFLOW_CONFIG),
        "provider_uri": "db/qlib_data",
        "date_min": (
            str(pred_all.index.get_level_values("datetime").min().date())
            if len(pred_all)
            else None
        ),
        "date_max": (
            str(pred_all.index.get_level_values("datetime").max().date())
            if len(pred_all)
            else None
        ),
        "total_rows": int(len(pred_all)),
        "total_trading_days": (
            int(pred_all.index.get_level_values("datetime").nunique())
            if len(pred_all)
            else 0
        ),
        "total_instruments": (
            int(pred_all.index.get_level_values("instrument").nunique())
            if len(pred_all)
            else 0
        ),
        "year_stats": year_stats,
        "output": str(out_path),
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OUT] {out_path}")
    print(f"[OUT] {meta_path}")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
