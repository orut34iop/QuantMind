#!/usr/bin/env python3
"""
Backfill missing Qlib feature bins from db/qlib_csv.

用途：
- 基于 CSV 原始数据为 qlib_data/features/<instrument>/ 补齐缺失字段。
- 默认仅补缺失文件，不覆盖已存在的 .day.bin。

说明：
- 采用 Qlib day bin 格式：首个 float32 为起始日历索引，后续为连续日值。
- 只处理数值列；自动跳过 date 与明显非数值元数据列。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_DIR = PROJECT_ROOT / "db" / "qlib_csv"
DEFAULT_QLIB_DIR = PROJECT_ROOT / "db" / "qlib_data"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "logs" / "qlib_feature_backfill_report.json"

# 训练与回测常用的 48 维因子所依赖的原始列（不含 date）。
# price/factor 相关表达式依赖 OHLCV + factor；若已存在不会覆盖。
TARGET_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "vwap",
    "volume",
    "amount",
    "factor",
    "Dretwd",
    "ChangeRatio",
    "pctChg",
    "RV",
    "RSkew",
    "RKurt",
    "SMB1",
    "HML1",
    "RiskPremium1",
    "B_Amount",
    "S_Amount",
    "B_Amount_L",
    "S_Amount_L",
    "B_Amount_S",
    "S_Amount_S",
    "B_Order",
    "S_Order",
    "B_AvgAmount",
    "S_AvgAmount",
    "AvgAmount",
    "Qsp_equal",
    "Esp_equal",
    "turn",
    "ToverOs",
    "VPIN",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "pcfNcfTTM",
    "isST",
    "ContinuedRiseDays",
    "ContinuedFallDays",
    "ContinuedLrgVolDs",
    "ContinuedShrinkageDs",
    "IsLifeHigh",
    "IsLifeLow",
    "IsBreakIssuePrice",
    "IsBreakNAVPS",
    "LifeHighMonth",
    "LifeLowMonth",
    "tradestatus",
]


def _load_calendar_index(cal_path: Path) -> tuple[list[pd.Timestamp], dict[pd.Timestamp, int]]:
    cal = pd.read_csv(cal_path, header=None, names=["date"])
    cal["date"] = pd.to_datetime(cal["date"])
    dates = cal["date"].tolist()
    idx_map = {d: i for i, d in enumerate(dates)}
    return dates, idx_map


def _iter_csv_files(csv_dir: Path, markets: list[str]) -> Iterable[Path]:
    # 仅处理股票目录，避免扫描文档类文件
    for market in markets:
        mdir = csv_dir / market
        if not mdir.exists():
            continue
        yield from mdir.glob("*.csv")


def _instrument_from_filename(path: Path) -> str:
    # sh600000.csv -> sh600000
    return path.stem.lower()


def _normalize_series(raw: pd.Series) -> pd.Series:
    # 将字符串数字（含百分号/空串）尽量转为 float
    def _clean(v: object) -> object:
        if pd.isna(v):
            return np.nan
        text = str(v).strip()
        if text in {"", "None", "nan", "NaN", "null", "NULL"}:
            return np.nan
        if text.endswith("%"):
            text = text[:-1]
        return text

    return pd.to_numeric(raw.map(_clean), errors="coerce")


def _build_bin_payload(
    dates: pd.Series,
    values: pd.Series,
    cal_index: dict[pd.Timestamp, int],
) -> np.ndarray | None:
    valid = pd.DataFrame({"date": dates, "val": values}).dropna(subset=["date"])
    if valid.empty:
        return None

    # 对齐到日历索引，丢弃不在交易日历内的日期
    valid["idx"] = valid["date"].map(cal_index)
    valid = valid.dropna(subset=["idx"])
    if valid.empty:
        return None

    valid["idx"] = valid["idx"].astype(int)
    valid = valid.sort_values("idx")

    start_idx = int(valid["idx"].iloc[0])
    end_idx = int(valid["idx"].iloc[-1])
    length = end_idx - start_idx + 1

    arr = np.full(length, np.nan, dtype=np.float32)
    for idx, val in zip(valid["idx"], valid["val"]):
        arr[int(idx) - start_idx] = np.float32(val)

    # qlib day bin: [start_idx, v1, v2, ...]
    payload = np.concatenate(([np.float32(start_idx)], arr))
    return payload.astype(np.float32)


def backfill(
    *,
    csv_dir: Path,
    qlib_dir: Path,
    report_path: Path,
    overwrite: bool,
    markets: list[str],
) -> dict:
    cal_path = qlib_dir / "calendars" / "day.txt"
    if not cal_path.exists():
        raise FileNotFoundError(f"Calendar file not found: {cal_path}")
    _, cal_index = _load_calendar_index(cal_path)

    feat_root = qlib_dir / "features"
    feat_root.mkdir(parents=True, exist_ok=True)

    summary = {
        "csv_files": 0,
        "instruments_processed": 0,
        "files_created": 0,
        "files_overwritten": 0,
        "files_skipped_existing": 0,
        "files_skipped_no_data": 0,
        "csv_failed": 0,
    }
    samples: list[dict] = []

    for csv_path in _iter_csv_files(csv_dir, markets):
        summary["csv_files"] += 1
        inst = _instrument_from_filename(csv_path)
        inst_dir = feat_root / inst
        inst_dir.mkdir(parents=True, exist_ok=True)

        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            summary["csv_failed"] += 1
            if len(samples) < 30:
                samples.append(
                    {
                        "instrument": inst,
                        "csv": str(csv_path),
                        "status": "csv_failed",
                        "error": str(exc),
                    }
                )
            continue

        if "date" not in df.columns:
            summary["csv_failed"] += 1
            if len(samples) < 30:
                samples.append(
                    {
                        "instrument": inst,
                        "csv": str(csv_path),
                        "status": "missing_date_column",
                    }
                )
            continue

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
        if df.empty:
            summary["csv_failed"] += 1
            continue

        created_for_inst = 0
        overwritten_for_inst = 0
        skipped_exist_for_inst = 0
        skipped_no_data_for_inst = 0

        for col in TARGET_COLUMNS:
            if col not in df.columns:
                skipped_no_data_for_inst += 1
                summary["files_skipped_no_data"] += 1
                continue

            out_path = inst_dir / f"{col.lower()}.day.bin"
            if out_path.exists() and not overwrite:
                skipped_exist_for_inst += 1
                summary["files_skipped_existing"] += 1
                continue

            vals = _normalize_series(df[col])
            payload = _build_bin_payload(df["date"], vals, cal_index)
            if payload is None or len(payload) <= 1:
                skipped_no_data_for_inst += 1
                summary["files_skipped_no_data"] += 1
                continue

            payload.tofile(out_path)
            if out_path.exists() and overwrite:
                overwritten_for_inst += 1
                summary["files_overwritten"] += 1
            else:
                created_for_inst += 1
                summary["files_created"] += 1

        summary["instruments_processed"] += 1
        if len(samples) < 30:
            samples.append(
                {
                    "instrument": inst,
                    "created": created_for_inst,
                    "overwritten": overwritten_for_inst,
                    "skipped_existing": skipped_exist_for_inst,
                    "skipped_no_data": skipped_no_data_for_inst,
                }
            )

    result = {
        "csv_dir": str(csv_dir),
        "qlib_dir": str(qlib_dir),
        "overwrite": overwrite,
        "markets": markets,
        "target_column_count": len(TARGET_COLUMNS),
        "target_columns": TARGET_COLUMNS,
        "summary": summary,
        "samples": samples,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing qlib feature bins from db/qlib_csv",
    )
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR))
    parser.add_argument("--qlib-dir", default=str(DEFAULT_QLIB_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing *.day.bin files (default: false)",
    )
    parser.add_argument(
        "--markets",
        nargs="+",
        default=["SH", "SZ"],
        help="CSV market folders to scan (default: SH SZ)",
    )
    args = parser.parse_args()

    result = backfill(
        csv_dir=Path(args.csv_dir),
        qlib_dir=Path(args.qlib_dir),
        report_path=Path(args.report),
        overwrite=args.overwrite,
        markets=[m.upper() for m in args.markets],
    )
    print(json.dumps({"report": args.report, "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
