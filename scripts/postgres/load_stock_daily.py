import argparse
import csv
import io
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv

DEFAULT_START_DATE = date(2025, 12, 1)
DEFAULT_END_DATE = date(2025, 12, 31)
LOOKBACK_TRADING_DAYS = 260
FALLBACK_WINDOW_DAYS = 400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load stock_daily with indicators from DuckDB into PostgreSQL."
    )
    parser.add_argument(
        "--duckdb-path",
        default=None,
        help="DuckDB file path (default: db/stock_new.duckdb).",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Start date in YYYY-MM-DD (default: 2025-12-01).",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="End date in YYYY-MM-DD (default: 2025-12-31).",
    )
    return parser.parse_args()


def load_env(project_root: Path) -> None:
    load_dotenv(project_root / ".env", override=False)


def get_pg_conn():
    host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST") or "localhost"
    port = int(os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT") or "5432")
    name = os.getenv("DB_NAME") or "quantmind"
    user = os.getenv("DB_USER") or "quantmind"
    password = os.getenv("DB_PASSWORD") or ""
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=name,
        user=user,
        password=password,
    )


def get_dates(
    start_date_value: str | None, end_date_value: str | None
) -> tuple[date, date]:
    start_date = (
        datetime.strptime(start_date_value, "%Y-%m-%d").date()
        if start_date_value
        else DEFAULT_START_DATE
    )
    end_date = (
        datetime.strptime(end_date_value, "%Y-%m-%d").date()
        if end_date_value
        else DEFAULT_END_DATE
    )
    if end_date < start_date:
        raise ValueError("end-date must be >= start-date")
    return start_date, end_date


def resolve_window_start(con: duckdb.DuckDBPyConnection, start_date: date) -> date:
    query = """
    select min(trading_date) as window_start
    from (
      select trading_date
      from trd_bwardquotation
      where trading_date < ?::date
      group by trading_date
      order by trading_date desc
      limit ?
    ) t
    """
    result = con.execute(query, [start_date, LOOKBACK_TRADING_DAYS]).fetchone()
    if result and result[0]:
        return result[0]
    return start_date - timedelta(days=FALLBACK_WINDOW_DAYS)


def ensure_schema(conn, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_month(value: date) -> date:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def ensure_partitions(conn, start_date: date, end_date: date) -> None:
    current = month_start(start_date)
    end_month = add_month(month_start(end_date))
    with conn.cursor() as cur:
        while current < end_month:
            next_month = add_month(current)
            partition_name = f"stock_daily_{current.year}{current.month:02d}"
            cur.execute(
                f"""
                create table if not exists {partition_name}
                partition of stock_daily
                for values from (%s) to (%s)
                """,
                (current, next_month),
            )
            current = next_month
    conn.commit()


def fetch_rows(duckdb_path: Path, start_date: date, end_date: date) -> pd.DataFrame:
    temp_dir = duckdb_path.parent / ".duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(
        str(duckdb_path),
        read_only=True,
        config={"temp_directory": str(temp_dir)},
    )
    window_start = resolve_window_start(con, start_date)
    query = """
    with params as (
      select ?::date as window_start, ?::date as end_date
    ),
    quotes as (
      select
        trading_date as trade_date,
        symbol,
        open_price as open,
        high_price as high,
        low_price as low,
        close_price as close,
        volume,
        amount,
        turnover_rate1 as turnover_rate,
        market_value
      from trd_bwardquotation
      where trading_date >= (select window_start from params)
        and trading_date <= (select end_date from params)
    ),
    quotes_mapped as (
      select
        q.*,
        coalesce(m.adjusted_symbol, q.symbol) as symbol_adj,
        case
          when length(regexp_replace(coalesce(m.adjusted_symbol, q.symbol), '[^0-9]', '', 'g')) = 0
            then null
          else lpad(
            regexp_replace(coalesce(m.adjusted_symbol, q.symbol), '[^0-9]', '', 'g'),
            6,
            '0'
          )
        end as ts_code
      from quotes q
      left join stock_code_mapping m
        on q.symbol = m.original_code
    ),
    valuation_source as (
      select
        case
          when length(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g'), 6, '0')
        end as stock_code_norm,
        date,
        pe_ratio_ttm,
        pb_ratio,
        1 as source_priority
      from relative_value_metrics_filled
      union all
      select
        case
          when length(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g'), 6, '0')
        end as stock_code_norm,
        date,
        pe_ratio_ttm,
        pb_ratio,
        2 as source_priority
      from fi_raw
    ),
    valuation as (
      select
        q.ts_code,
        q.trade_date,
        v.pe_ratio_ttm,
        v.pb_ratio
      from quotes_mapped q
      left join valuation_source v
        on v.stock_code_norm = q.ts_code
       and v.date <= q.trade_date
      qualify row_number() over (
        partition by q.ts_code, q.trade_date
        order by v.date desc, v.source_priority asc
      ) = 1
    )
    select
      q.ts_code,
      q.trade_date,
      q.open,
      q.high,
      q.low,
      q.close,
      q.volume,
      q.amount,
      q.turnover_rate,
      q.market_value,
      v.pe_ratio_ttm,
      v.pb_ratio
    from quotes_mapped q
    left join valuation v
      on v.ts_code = q.ts_code
     and v.trade_date = q.trade_date
    where q.ts_code is not null
    order by q.ts_code, q.trade_date
    """
    rows = con.execute(query, [window_start, end_date]).fetchdf()
    con.close()
    return rows


def compute_indicators(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    rows = rows.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    rows["trade_date"] = pd.to_datetime(rows["trade_date"]).dt.date

    def sma(series: pd.Series, length: int) -> pd.Series:
        return series.rolling(length, min_periods=length).mean()

    def ema(series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False, min_periods=length).mean()

    def rsi(series: pd.Series, length: int) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / length, adjust=False,
                            min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, adjust=False,
                            min_periods=length).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def stoch_kd(
        high: pd.Series, low: pd.Series, close: pd.Series
    ) -> tuple[pd.Series, pd.Series]:
        lowest_low = low.rolling(9, min_periods=9).min()
        highest_high = high.rolling(9, min_periods=9).max()
        fast_k = (close - lowest_low) / (highest_high - lowest_low) * 100
        slow_k = fast_k.rolling(3, min_periods=3).mean()
        slow_d = slow_k.rolling(3, min_periods=3).mean()
        return slow_k, slow_d

    def cci(
        high: pd.Series, low: pd.Series, close: pd.Series, length: int
    ) -> pd.Series:
        tp = (high + low + close) / 3
        ma = tp.rolling(length, min_periods=length).mean()
        md = (tp - ma).abs().rolling(length, min_periods=length).mean()
        return (tp - ma) / (0.015 * md)

    def willr(
        high: pd.Series, low: pd.Series, close: pd.Series, length: int
    ) -> pd.Series:
        highest_high = high.rolling(length, min_periods=length).max()
        lowest_low = low.rolling(length, min_periods=length).min()
        return (highest_high - close) / (highest_high - lowest_low) * -100

    def atr(
        high: pd.Series, low: pd.Series, close: pd.Series, length: int
    ) -> pd.Series:
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(length, min_periods=length).mean()

    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        direction = np.sign(close.diff()).fillna(0)
        return (direction * volume).cumsum()

    def apply_group(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("trade_date").copy()
        close = group["close"]
        high = group["high"]
        low = group["low"]
        volume = group["volume"]

        group["ma5"] = sma(close, 5)
        group["ma10"] = sma(close, 10)
        group["ma20"] = sma(close, 20)
        group["ma60"] = sma(close, 60)
        group["ma120"] = sma(close, 120)
        group["ma250"] = sma(close, 250)

        group["ema12"] = ema(close, 12)
        group["ema26"] = ema(close, 26)
        group["dif"] = group["ema12"] - group["ema26"]
        group["dea"] = ema(group["dif"], 9)
        group["macd"] = (group["dif"] - group["dea"]) * 2

        ma20 = group["ma20"]
        std20 = close.rolling(20, min_periods=20).std(ddof=0)
        group["boll_mid"] = ma20
        group["boll_upper"] = ma20 + 2 * std20
        group["boll_lower"] = ma20 - 2 * std20

        group["rsi_6"] = rsi(close, 6)
        group["rsi_12"] = rsi(close, 12)
        group["rsi_14"] = rsi(close, 14)

        group["stoch_k"], group["stoch_d"] = stoch_kd(high, low, close)
        group["kdj_k"] = group["stoch_k"]
        group["kdj_d"] = group["stoch_d"]
        group["kdj_j"] = group["kdj_k"] * 3 - group["kdj_d"] * 2

        group["cci_14"] = cci(high, low, close, length=14)
        group["willr_14"] = willr(high, low, close, length=14)
        group["atr_14"] = atr(high, low, close, length=14)
        group["obv"] = obv(close, volume)

        log_ret = np.log(close / close.shift(1))
        group["volatility_20"] = log_ret.rolling(20).std(ddof=0) * np.sqrt(252)

        group["vol_ma5"] = volume.rolling(5).mean()
        group["vol_ratio"] = volume / group["vol_ma5"]

        group["is_vol_up_3d"] = (volume > volume.shift(1)) & (
            volume.shift(1) > volume.shift(2)
        )
        group["is_ma5_above_ma20"] = group["ma5"] > group["ma20"]
        group["is_kdj_golden_cross"] = (group["kdj_k"] > group["kdj_d"]) & (
            group["kdj_k"].shift(1) <= group["kdj_d"].shift(1)
        )
        group["is_stoch_golden_cross"] = (group["stoch_k"] > group["stoch_d"]) & (
            group["stoch_k"].shift(1) <= group["stoch_d"].shift(1)
        )
        group["close_above_vwap"] = group["close"] >= group["vwap"]

        return group

    rows = rows.groupby("ts_code", group_keys=False).apply(
        apply_group, include_groups=False
    )
    if "ts_code" not in rows.columns:
        rows = rows.reset_index()
        if "level_0" in rows.columns:
            rows = rows.rename(columns={"level_0": "ts_code"})
    return rows


def write_rows(conn, rows: pd.DataFrame, start_date: date, end_date: date) -> int:
    if rows.empty:
        return 0

    rows["amount"] = pd.to_numeric(rows["amount"], errors="coerce")
    rows["market_value"] = pd.to_numeric(rows["market_value"], errors="coerce")
    rows["total_mv"] = rows["market_value"] / 1e8
    rows["amount_wan"] = rows["amount"] / 10000
    rows["vwap"] = rows["amount"] / rows["volume"].replace(0, np.nan)
    rows["amount"] = rows["amount_wan"]
    rows["pe_ttm"] = rows.get("pe_ratio_ttm")
    rows["pb"] = rows.get("pb_ratio")
    rows["roe"] = None
    rows["eps"] = None

    rows = compute_indicators(rows)
    rows = rows[
        (rows["trade_date"] >= start_date) & (rows["trade_date"] <= end_date)
    ].copy()
    if "ts_code" not in rows.columns:
        if "index" in rows.columns:
            rows["ts_code"] = rows["index"]
        else:
            rows["ts_code"] = rows.index.astype(str)
    rows["ts_code"] = rows["ts_code"].astype(str).str.strip()
    rows = rows[rows["ts_code"].notna() & (rows["ts_code"] != "")]

    numeric_round_2 = [
        "open",
        "high",
        "low",
        "close",
        "total_mv",
        "amount",
        "turnover_rate",
        "ma5",
        "ma10",
        "ma20",
        "ma60",
        "ma120",
        "ma250",
        "ema12",
        "ema26",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "rsi_6",
        "rsi_12",
        "rsi_14",
        "kdj_k",
        "kdj_d",
        "kdj_j",
        "stoch_k",
        "stoch_d",
        "cci_14",
        "willr_14",
        "atr_14",
        "vwap",
    ]
    for col in numeric_round_2:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").round(2)

    numeric_round_4 = ["pe_ttm", "pb", "vol_ratio"]
    for col in numeric_round_4:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").round(4)

    numeric_round_6 = ["volatility_20", "dif", "dea", "macd"]
    for col in numeric_round_6:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").round(6)

    bigint_columns = ["volume", "vol_ma5", "obv"]
    for col in bigint_columns:
        if col in rows.columns:
            rows[col] = (
                pd.to_numeric(
                    rows[col], errors="coerce").round().astype("Int64")
            )

    columns = [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "total_mv",
        "pe_ttm",
        "pb",
        "roe",
        "eps",
        "turnover_rate",
        "ma5",
        "ma10",
        "ma20",
        "ma60",
        "ma120",
        "ma250",
        "ema12",
        "ema26",
        "dif",
        "dea",
        "macd",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "rsi_6",
        "rsi_12",
        "rsi_14",
        "kdj_k",
        "kdj_d",
        "kdj_j",
        "stoch_k",
        "stoch_d",
        "cci_14",
        "willr_14",
        "atr_14",
        "volatility_20",
        "vol_ma5",
        "vol_ratio",
        "obv",
        "vwap",
        "is_vol_up_3d",
        "is_ma5_above_ma20",
        "is_kdj_golden_cross",
        "is_stoch_golden_cross",
        "close_above_vwap",
    ]

    for col in columns:
        if col not in rows.columns:
            rows[col] = None

    rows = rows.astype(object).where(pd.notnull(rows), None)
    with conn.cursor() as cur:
        cur.execute(
            "delete from stock_daily where trade_date >= %s and trade_date <= %s",
            (start_date, end_date),
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerows(rows[columns].itertuples(index=False, name=None))
        buffer.seek(0)
        copy_sql = (
<<<<<<< HEAD
            "copy stock_daily (" + ", ".join(columns) + ") from stdin with (format csv)"
=======
            "copy stock_daily (" + ", ".join(columns) +
            ") from stdin with (format csv)"
>>>>>>> refactor/service-cleanup
        )
        cur.copy_expert(copy_sql, buffer)
    conn.commit()
    return len(rows)


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    load_env(project_root)

    duckdb_path = (
        Path(args.duckdb_path)
        if args.duckdb_path
        else project_root / "db" / "stock_new.duckdb"
    )
    if not duckdb_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    start_date, end_date = get_dates(args.start_date, args.end_date)
    schema_path = Path(__file__).with_name("stock_daily.sql")

    with get_pg_conn() as conn:
        ensure_schema(conn, schema_path)
        ensure_partitions(conn, start_date, end_date)
        rows = fetch_rows(duckdb_path, start_date, end_date)
        inserted = write_rows(conn, rows, start_date, end_date)

    print(
        "Loaded stock_daily rows:",
        inserted,
        "range:",
        start_date,
        "to",
        end_date,
    )


if __name__ == "__main__":
    main()
