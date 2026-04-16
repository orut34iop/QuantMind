#!/usr/bin/env python3
"""
从 feature_snapshots 提取训练可用特征列（不依赖 alpha158 配置）。

能力：
1. 支持从本地目录读取 parquet schema
2. 支持从 COS 下载 parquet 后读取 schema
3. 按年份交集筛选，确保所选特征在所有指定年份均存在
4. 输出前 N 个特征（默认 48）到 stdout / 文件
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, List, Set

import pyarrow.parquet as pq

try:
    from qcloud_cos import CosConfig, CosS3Client
except Exception:  # noqa: BLE001
    CosConfig = None
    CosS3Client = None


DEFAULT_IGNORE_COLS: Set[str] = {
    "symbol",
    "trade_date",
    "date",
    "datetime",
    "label",
    "target",
    "y",
}


def _parse_years(raw: str) -> List[int]:
    years: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        years.append(int(token))
    if not years:
        raise ValueError("years cannot be empty")
    return years


def _schema_cols_from_parquet(path: Path) -> List[str]:
    pf = pq.ParquetFile(path)
    return list(pf.schema_arrow.names)


def _cos_client_from_env() -> CosS3Client:
    if CosConfig is None or CosS3Client is None:
        raise RuntimeError("cos-python-sdk-v5 is not installed")

    region = os.getenv("TENCENT_REGION", "").strip()
    sid = os.getenv("TENCENT_SECRET_ID", "").strip()
    sk = os.getenv("TENCENT_SECRET_KEY", "").strip()
    if not (region and sid and sk):
        raise RuntimeError("missing TENCENT_REGION / TENCENT_SECRET_ID / TENCENT_SECRET_KEY")

    return CosS3Client(
        CosConfig(
            Region=region,
            SecretId=sid,
            SecretKey=sk,
            Scheme="https",
            # 在腾讯云同地域环境下优先使用内网访问 COS，避免公网流量成本。
            EnableInternalDomain=True,
            AutoSwitchDomainOnRetry=True,
        )
    )


def _download_one_snapshot(bucket: str, key: str, dst: Path) -> None:
    client = _cos_client_from_env()
    client.download_file(Bucket=bucket, Key=key, DestFilePath=str(dst))


def _ordered_intersection(col_lists: List[List[str]]) -> List[str]:
    if not col_lists:
        return []
    base = col_lists[0]
    common = set(base)
    for cols in col_lists[1:]:
        common &= set(cols)
    return [c for c in base if c in common]


def _filter_candidates(cols: Iterable[str], ignore_cols: Set[str]) -> List[str]:
    out: List[str] = []
    for col in cols:
        if not col:
            continue
        lc = col.strip().lower()
        if lc in ignore_cols:
            continue
        if lc.startswith("__index"):
            continue
        out.append(col)
    return out


def _load_year_cols_from_local(local_dir: Path, years: List[int]) -> List[List[str]]:
    col_lists: List[List[str]] = []
    for year in years:
        path = local_dir / f"model_features_{year}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"snapshot not found: {path}")
        col_lists.append(_schema_cols_from_parquet(path))
    return col_lists


def _load_year_cols_from_cos(bucket: str, prefix: str, years: List[int]) -> List[List[str]]:
    col_lists: List[List[str]] = []
    with tempfile.TemporaryDirectory(prefix="snapshot_schema_") as td:
        tmp_dir = Path(td)
        for year in years:
            key = f"{prefix.rstrip('/')}/model_features_{year}.parquet"
            dst = tmp_dir / f"model_features_{year}.parquet"
            _download_one_snapshot(bucket, key, dst)
            col_lists.append(_schema_cols_from_parquet(dst))
    return col_lists


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract feature list from feature_snapshots parquet schemas")
    parser.add_argument("--years", default="2020,2021,2022,2023,2024,2025", help="Comma-separated years")
    parser.add_argument("--count", type=int, default=48, help="Number of features to output")
    parser.add_argument("--bucket", default=os.getenv("TENCENT_BUCKET", ""), help="COS bucket")
    parser.add_argument("--cos-prefix", default="feature_snapshots", help="COS prefix for snapshots")
    parser.add_argument("--local-dir", default="", help="Use local snapshot dir instead of COS")
    parser.add_argument("--output", default="", help="Output JSON file path")
    parser.add_argument("--print-meta", action="store_true", help="Print meta info to stderr")
    args = parser.parse_args()

    years = _parse_years(args.years)
    if args.count <= 0:
        raise ValueError("count must be > 0")

    if args.local_dir:
        col_lists = _load_year_cols_from_local(Path(args.local_dir), years)
    else:
        bucket = args.bucket.strip()
        if not bucket:
            raise RuntimeError("bucket is required when local-dir is empty")
        col_lists = _load_year_cols_from_cos(bucket=bucket, prefix=args.cos_prefix, years=years)

    common_cols = _ordered_intersection(col_lists)
    candidates = _filter_candidates(common_cols, DEFAULT_IGNORE_COLS)
    selected = candidates[: args.count]

    if len(selected) < args.count:
        raise RuntimeError(
            f"only {len(selected)} usable columns found, less than requested count={args.count}; "
            f"try reducing count or checking snapshot schemas"
        )

    payload = {
        "source": "local" if args.local_dir else "cos",
        "years": years,
        "feature_count": len(selected),
        "features": selected,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
