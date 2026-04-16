import argparse
import os
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_COLUMNS = [
    "timestamp",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "amount",  # Keep amount for now, will rename later to factor
]


def build_db_url() -> str:
    # Prefer full DATABASE_URL if provided
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
    port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    missing = [k for k, v in (
        ("DB_HOST", host), ("DB_PORT", port), ("DB_NAME", name), ("DB_USER", user), ("DB_PASSWORD", password)
    ) if not v]
    if missing:
        raise RuntimeError(f"Missing database environment variables: {', '.join(missing)}. Set DATABASE_URL or DB_* vars in root .env")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def fetch_symbols(
    engine, table: str, interval: str, start: Optional[str], end: Optional[str]
) -> Iterable[str]:
    sql = f"SELECT DISTINCT symbol FROM {table} WHERE interval = :interval"
    params = {"interval": interval}
    if start:
        sql += " AND timestamp >= :start"
        params["start"] = start
    if end:
        sql += " AND timestamp <= :end"
        params["end"] = end
    df = pd.read_sql_query(text(sql), engine, params=params)
    return df["symbol"].dropna().astype(str).tolist()


def export_symbol(
    engine,
    table: str,
    symbol: str,
    interval: str,
    start: Optional[str],
    end: Optional[str],
    output_dir: Path,
    include_symbol: bool,
) -> int:
    sql = (
        f"SELECT {', '.join(DEFAULT_COLUMNS)}, symbol "
        f"FROM {table} WHERE symbol = :symbol AND interval = :interval"
    )
    params = {"symbol": symbol, "interval": interval}
    if start:
        sql += " AND timestamp >= :start"
        params["start"] = start
    if end:
        sql += " AND timestamp <= :end"
        params["end"] = end
    sql += " ORDER BY timestamp"

    df = pd.read_sql_query(text(sql), engine, params=params)
    if df.empty:
        return 0

    df = df.rename(
        columns={
            "timestamp": "date",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
            "amount": "factor",  # Rename amount to factor for Qlib compatibility
            "symbol": "instrument",  # Rename symbol to instrument for Qlib compatibility
        }
    )

    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # Always include the 'instrument' column for Qlib compatibility.
    # The 'include_symbol' argument is effectively ignored here.

    output_path = output_dir / f"{symbol}.csv"
    df.to_csv(output_path, index=False)
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export klines table to Qlib-style CSV per symbol."
    )
    parser.add_argument(
        "--table", default=os.getenv("QLIB_KLINES_TABLE", "klines"))
    parser.add_argument(
        "--interval", default=os.getenv("QLIB_KLINES_INTERVAL", "1d"))
    parser.add_argument("--start", default=os.getenv("QLIB_START_DATE"))
    parser.add_argument("--end", default=os.getenv("QLIB_END_DATE"))
    parser.add_argument(
        "--output-dir",
        default=os.getenv("QLIB_RAW_DIR", "research/data_adapter/raw/1d"),
    )
    # Removed --include-symbol as it is now always True for Qlib compatibility
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(build_db_url())

    symbols = fetch_symbols(
        engine, args.table, args.interval, args.start, args.end)
    total_rows = 0
    for symbol in symbols:
        rows = export_symbol(
            engine,
            args.table,
            symbol,
            args.interval,
            args.start,
            args.end,
            output_dir,
            # Always include symbol (now instrument) for Qlib compatibility
            True,
        )
        total_rows += rows
        print(f"Exported {rows} rows for {symbol}")

    print(f"Done. Symbols: {len(symbols)}, Rows: {total_rows}")


if __name__ == "__main__":
    main()
