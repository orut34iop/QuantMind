#!/usr/bin/env python3
"""Merge feature snapshots with next-day return labels for training.

输入:
- db/feature_snapshots/features_YYYY.parquet
- db/csmar_data.duckdb 中的 "股票历史日行情信息表后复权"

输出:
- db/feature_snapshots/model_features_YYYY.parquet
- db/feature_snapshots/model_features_YYYY_report.json
- db/feature_snapshots/merge_summary.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb


LOGGER = logging.getLogger("merge_features_with_labels")
YEAR_PATTERN = re.compile(r"features_(\d{4})\.parquet$")
SOURCE_TABLE = "日个股回报率文件"


@dataclass(frozen=True)
class FeatureFile:
    year: int
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge feature snapshots with T+1 close return labels."
    )
    parser.add_argument(
        "--feature-glob",
        default="db/feature_snapshots/features_*.parquet",
        help="Feature parquet glob path.",
    )
    parser.add_argument(
        "--db-path",
        default="db/csmar_data.duckdb",
        help="DuckDB path with source close prices.",
    )
    parser.add_argument(
        "--out-dir",
        default="db/feature_snapshots",
        help="Output directory.",
    )
    parser.add_argument(
        "--years",
        nargs="*",
        type=int,
        default=None,
        help="Optional year filter, e.g. --years 2024 2025",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=8,
        help="DuckDB thread count.",
    )
    parser.add_argument(
        "--sample-symbols",
        type=int,
        default=5,
        help="Validation sample symbol count for each output file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing model_features_YYYY.parquet files.",
    )
    return parser.parse_args()


def discover_feature_files(pattern: str, years: set[int] | None) -> list[FeatureFile]:
    files: list[FeatureFile] = []
    for path in sorted(Path().glob(pattern)):
        match = YEAR_PATTERN.search(path.name)
        if not match:
            continue
        year = int(match.group(1))
        if years and year not in years:
            continue
        files.append(FeatureFile(year=year, path=path.resolve()))
    return files


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def query_single_value(con: duckdb.DuckDBPyConnection, sql: str) -> float | int | str | None:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def get_columns(con: duckdb.DuckDBPyConnection, parquet_path: Path) -> list[str]:
    sql = (
        "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet("
        f"'{parquet_path.as_posix()}')) ORDER BY column_name"
    )
    return [str(row[0]) for row in con.execute(sql).fetchall()]


def build_null_ratio_sql(columns: Iterable[str], parquet_path: Path) -> str:
    exprs = [
        f"AVG(CASE WHEN {quote_ident(col)} IS NULL THEN 1.0 ELSE 0.0 END) AS {quote_ident(col)}"
        for col in columns
    ]
    return (
        "SELECT " + ", ".join(exprs) + " "
        f"FROM read_parquet('{parquet_path.as_posix()}')"
    )


def ensure_output_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)


def create_labels_temp_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE labels AS
        SELECT
            CASE
              WHEN LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '6%' THEN 'SH' || LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0')
              WHEN LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '0%' OR LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0') LIKE '3%' THEN 'SZ' || LPAD(RIGHT(CAST(Stkcd AS VARCHAR), 6), 6, '0')
            END AS symbol,
            Trddt AS trade_date,
            LEAD(Dretwd) OVER (
                PARTITION BY Stkcd
                ORDER BY Trddt
            ) AS label
        FROM csmar.{quote_ident(SOURCE_TABLE)}
        """
    )


def process_year(
    con: duckdb.DuckDBPyConnection,
    feature_file: FeatureFile,
    out_dir: Path,
    sample_symbols: int,
    force: bool,
) -> dict[str, object]:
    out_path = (out_dir / f"model_features_{feature_file.year}.parquet").resolve()
    report_path = (out_dir / f"model_features_{feature_file.year}_report.json").resolve()

    if out_path.exists() and not force:
        raise FileExistsError(f"Output exists, use --force to overwrite: {out_path}")

    LOGGER.info("Processing year=%s, file=%s", feature_file.year, feature_file.path)
    con.execute("DROP TABLE IF EXISTS feat_raw")
    con.execute("DROP TABLE IF EXISTS feat_dedup")

    con.execute(
        f"""
        CREATE TEMP TABLE feat_raw AS
        SELECT *
        FROM read_parquet('{feature_file.path.as_posix()}')
        """
    )

    raw_rows = int(query_single_value(con, "SELECT COUNT(*) FROM feat_raw") or 0)
    raw_keys = int(
        query_single_value(
            con,
            """
            SELECT COUNT(DISTINCT struct_pack(symbol := symbol, trade_date := trade_date))
            FROM feat_raw
            """,
        )
        or 0
    )
    duplicate_rows_removed = raw_rows - raw_keys

    con.execute(
        """
        CREATE TEMP TABLE feat_dedup AS
        SELECT * EXCLUDE(_rn)
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, trade_date
                    ORDER BY symbol, trade_date
                ) AS _rn
            FROM feat_raw
        ) t
        WHERE _rn = 1
        """
    )

    con.execute(
        f"""
        COPY (
            SELECT
                f.*,
                l.label
            FROM feat_dedup f
            LEFT JOIN labels l
                ON f.symbol = l.symbol
               AND f.trade_date = l.trade_date
            ORDER BY f.trade_date, f.symbol
        ) TO '{out_path.as_posix()}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    out_rows = int(
        query_single_value(
            con,
            f"SELECT COUNT(*) FROM read_parquet('{out_path.as_posix()}')",
        )
        or 0
    )

    in_cols = get_columns(con, feature_file.path)
    out_cols = get_columns(con, out_path)
    expected_feature_count = len(in_cols) - 2
    actual_feature_count = len(out_cols) - 3

    sample_symbol_sql = f"""
        WITH syms AS (
            SELECT DISTINCT symbol
            FROM read_parquet('{out_path.as_posix()}')
            ORDER BY hash(symbol)
            LIMIT {int(sample_symbols)}
        ),
        sampled AS (
            SELECT
                o.symbol,
                o.trade_date,
                o.label
            FROM read_parquet('{out_path.as_posix()}') o
            JOIN syms s ON o.symbol = s.symbol
        )
        SELECT
            COUNT(*) AS checked_rows,
            SUM(CASE WHEN label IS NOT NULL THEN 1 ELSE 0 END) AS matched_rows
        FROM sampled
    """
    checked_rows, matched_rows = con.execute(sample_symbol_sql).fetchone()

    null_ratio_cols = [c for c in out_cols if c not in ("symbol", "trade_date")]
    null_ratio_sql = build_null_ratio_sql(null_ratio_cols, out_path)
    null_ratio_row = con.execute(null_ratio_sql).fetchone()
    null_ratios = {
        col: float(val) if val is not None else 1.0
        for col, val in zip(null_ratio_cols, null_ratio_row)
    }
    max_null_feature = max(
        (c for c in null_ratio_cols if c != "label"),
        key=lambda c: null_ratios[c],
    )

    report: dict[str, object] = {
        "year": feature_file.year,
        "input_file": feature_file.path.as_posix(),
        "output_file": out_path.as_posix(),
        "raw_rows": raw_rows,
        "raw_unique_symbol_trade_date": raw_keys,
        "duplicate_rows_removed": duplicate_rows_removed,
        "output_rows": out_rows,
        "input_column_count": len(in_cols),
        "output_column_count": len(out_cols),
        "expected_feature_count": expected_feature_count,
        "actual_feature_count": actual_feature_count,
        "has_label_column": "label" in out_cols,
        "sample_label_check_rows": int(checked_rows or 0),
        "sample_label_matched_rows": int(matched_rows or 0),
        "sample_label_match_ratio": (
            float(matched_rows) / float(checked_rows) if checked_rows else 0.0
        ),
        "label_null_ratio": null_ratios.get("label", 1.0),
        "max_feature_null_ratio": float(null_ratios[max_null_feature]),
        "max_null_feature": max_null_feature,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    LOGGER.info(
        "Finished year=%s rows=%s duplicates_removed=%s report=%s",
        feature_file.year,
        out_rows,
        duplicate_rows_removed,
        report_path,
    )
    return report


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    years = set(args.years) if args.years else None
    feature_files = discover_feature_files(args.feature_glob, years)
    if not feature_files:
        raise FileNotFoundError(f"No feature files found with pattern: {args.feature_glob}")

    out_dir = Path(args.out_dir).resolve()
    ensure_output_dir(out_dir)

    con = duckdb.connect()
    con.execute(f"PRAGMA threads={int(args.threads)}")
    con.execute("PRAGMA temp_directory='tmp'")
    con.execute(f"ATTACH '{Path(args.db_path).resolve().as_posix()}' AS csmar (READ_ONLY)")
    create_labels_temp_table(con)

    summary_reports: list[dict[str, object]] = []
    for feature_file in feature_files:
        report = process_year(
            con=con,
            feature_file=feature_file,
            out_dir=out_dir,
            sample_symbols=args.sample_symbols,
            force=args.force,
        )
        summary_reports.append(report)

    total_rows = sum(int(r["output_rows"]) for r in summary_reports)
    total_dup_removed = sum(int(r["duplicate_rows_removed"]) for r in summary_reports)
    summary = {
        "feature_glob": args.feature_glob,
        "db_path": str(Path(args.db_path).resolve()),
        "out_dir": out_dir.as_posix(),
        "years": [int(r["year"]) for r in summary_reports],
        "total_output_rows": total_rows,
        "total_duplicate_rows_removed": total_dup_removed,
        "reports": summary_reports,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = out_dir / "merge_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("All done. summary=%s", summary_path)


if __name__ == "__main__":
    main()
