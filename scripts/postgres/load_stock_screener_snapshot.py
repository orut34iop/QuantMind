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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load stock screener snapshot data from DuckDB into PostgreSQL."
    )
    parser.add_argument(
        "--duckdb-path",
        default=None,
        help="DuckDB file path (default: db/stock_new.duckdb).",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="Snapshot end date in YYYY-MM-DD (default: today).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=31,
        help="Number of days to keep (default: 31).",
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


def get_dates(as_of_date_value: str | None, days: int) -> tuple[date, date, date]:
    if as_of_date_value:
        as_of = datetime.strptime(as_of_date_value, "%Y-%m-%d").date()
    else:
        as_of = date.today()
    start_date = as_of - timedelta(days=days - 1)
    window_start = start_date - timedelta(days=90)
    return window_start, start_date, as_of


def ensure_schema(conn, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()


def fetch_rows(
    duckdb_path: Path, window_start: date, start_date: date, end_date: date
) -> pd.DataFrame:
    temp_dir = duckdb_path.parent / ".duckdb_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(
        str(duckdb_path),
        read_only=True,
        config={"temp_directory": str(temp_dir)},
    )
    query = """
    with params as (
      select ?::date as window_start, ?::date as start_date, ?::date as end_date
    ),
    quotes as (
      select
        trading_date as snapshot_date,
        symbol,
        short_name,
        open_price,
        close_price,
        high_price,
        low_price,
        volume,
        amount,
        avg_price,
        change_ratio,
        turnover_rate1,
        market_value,
        circulated_market_value,
        total_share,
        circulated_share,
        a_circulated_share,
        b_circulated_share,
        a_value,
        b_value
      from trd_bwardquotation
      where trading_date >= (select window_start from params)
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
        end as symbol_norm
      from quotes q
      left join stock_code_mapping m
        on q.symbol = m.original_code
    ),
    quotes_window as (
      select
        snapshot_date,
        symbol_norm as symbol,
        short_name,
        open_price,
        close_price,
        high_price,
        low_price,
        volume,
        amount,
        avg_price,
        change_ratio,
        turnover_rate1,
        market_value,
        circulated_market_value,
        total_share,
        circulated_share,
        a_circulated_share,
        b_circulated_share,
        a_value,
        b_value,
        volume as vol_1d,
        sum(volume) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 2 preceding and current row
        ) as vol_3d_sum,
        case
          when lag(volume, 2) over (partition by symbol_norm order by snapshot_date) is null
            then false
          when volume > lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
             > lag(volume, 2) over (partition by symbol_norm order by snapshot_date)
            then true
          else false
        end as vol_3d_up,
        case
          when lag(volume, 2) over (partition by symbol_norm order by snapshot_date) is null
            then 0
          when volume > lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
             > lag(volume, 2) over (partition by symbol_norm order by snapshot_date)
            then 1
          when volume < lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
             < lag(volume, 2) over (partition by symbol_norm order by snapshot_date)
            then -1
          else 0
        end as vol_3d_trend,
        sum(amount) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 2 preceding and current row
        ) as amount_3d_sum,
        close_price
          - lag(close_price, 2) over (partition by symbol_norm order by snapshot_date)
          as price_3d_change
        ,sum(volume) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as vol_5d_sum
        ,avg(volume) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as vol_5d_avg
        ,case
          when lag(volume, 4) over (partition by symbol_norm order by snapshot_date) is null
            then false
          when volume > lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 1) over (partition by symbol_norm order by snapshot_date)
             > lag(volume, 2) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 2) over (partition by symbol_norm order by snapshot_date)
             > lag(volume, 3) over (partition by symbol_norm order by snapshot_date)
           and lag(volume, 3) over (partition by symbol_norm order by snapshot_date)
             > lag(volume, 4) over (partition by symbol_norm order by snapshot_date)
            then true
          else false
        end as vol_5d_up
        ,sum(amount) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as amount_5d_sum
        ,close_price
          - lag(close_price, 4) over (partition by symbol_norm order by snapshot_date)
          as price_5d_change
        ,case
          when lag(close_price, 4) over (partition by symbol_norm order by snapshot_date) is null
            then null
          else close_price
            / lag(close_price, 4) over (partition by symbol_norm order by snapshot_date)
            - 1
        end as return_5d
        ,case
          when lag(close_price, 9) over (partition by symbol_norm order by snapshot_date) is null
            then null
          else close_price
            / lag(close_price, 9) over (partition by symbol_norm order by snapshot_date)
            - 1
        end as return_10d
        ,avg(close_price) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as ma5
        ,avg(close_price) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 9 preceding and current row
        ) as ma10
        ,max(high_price) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as high_5d
        ,min(low_price) over (
          partition by symbol_norm
          order by snapshot_date
          rows between 4 preceding and current row
        ) as low_5d
        ,case
          when avg(close_price) over (
            partition by symbol_norm
            order by snapshot_date
            rows between 4 preceding and current row
          ) is null
            then null
          else close_price >= avg(close_price) over (
            partition by symbol_norm
            order by snapshot_date
            rows between 4 preceding and current row
          )
        end as close_above_ma5
        ,case
          when avg(close_price) over (
            partition by symbol_norm
            order by snapshot_date
            rows between 9 preceding and current row
          ) is null
            then null
          else close_price >= avg(close_price) over (
            partition by symbol_norm
            order by snapshot_date
            rows between 9 preceding and current row
          )
        end as close_above_ma10
      from quotes_mapped
    ),
    valuation_source as (
      select
        case
          when length(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(cast(stock_code as varchar), '[^0-9]', '', 'g'), 6, '0')
        end as stock_code_norm,
        date,
        quarter,
        pe_ratio_1,
        pe_ratio_2,
        pe_ratio_ttm,
        pb_ratio,
        pb_ratio_parent,
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
        quarter,
        pe_ratio_1,
        pe_ratio_2,
        pe_ratio_ttm,
        pb_ratio,
        pb_ratio_parent,
        2 as source_priority
      from fi_raw
    ),
    valuation as (
      select
        q.symbol,
        q.snapshot_date,
        v.pe_ratio_1,
        v.pe_ratio_2,
        v.pe_ratio_ttm,
        v.pb_ratio,
        v.pb_ratio_parent,
        v.quarter
      from quotes_window q
      left join valuation_source v
        on v.stock_code_norm = q.symbol
       and v.date <= q.snapshot_date
      qualify row_number() over (
        partition by q.symbol, q.snapshot_date
        order by v.date desc, v.source_priority asc
      ) = 1
    ),
    trend as (
      select
        trading_date as snapshot_date,
        case
          when length(regexp_replace(symbol, '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(symbol, '[^0-9]', '', 'g'), 6, '0')
        end as symbol_norm,
        securityid,
        continued_rise_days,
        continued_fall_days,
        life_high,
        life_low,
        life_high_week,
        life_high_month,
        life_high_3month,
        life_high_6month,
        life_high_one_year,
        life_low_week,
        life_low_month,
        life_low_3month,
        life_low_6month,
        life_low_one_year
      from trd_stocktrend
      where trading_date >= (select window_start from params)
    ),
    adjust_source as (
      select
        case
          when length(regexp_replace(symbol, '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(symbol, '[^0-9]', '', 'g'), 6, '0')
        end as symbol_norm,
        trading_date,
        fward_factor,
        bward_factor,
        cumulate_fward_factor,
        cumulate_bward_factor,
        1 as source_priority
      from trd_adjustfactor
      where trading_date >= (select window_start from params)
      union all
      select
        case
          when length(regexp_replace(coalesce(adjusted_symbol, raw_symbol), '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(coalesce(adjusted_symbol, raw_symbol), '[^0-9]', '', 'g'), 6, '0')
        end as symbol_norm,
        trading_date,
        coalesce(
          fward_factor,
          nullif(fward_close_price, 0) / nullif(close_price, 0)
        ) as fward_factor,
        coalesce(
          bward_factor,
          nullif(bward_close_price, 0) / nullif(close_price, 0)
        ) as bward_factor,
        coalesce(
          cumulate_fward_factor,
          nullif(fward_close_price, 0) / nullif(close_price, 0)
        ) as cumulate_fward_factor,
        coalesce(
          cumulate_bward_factor,
          nullif(bward_close_price, 0) / nullif(close_price, 0)
        ) as cumulate_bward_factor,
        2 as source_priority
      from stock_price_adjusted_clean
      where trading_date >= (select window_start from params)
    ),
    adjust as (
      select
        q.symbol,
        q.snapshot_date,
        a.fward_factor,
        a.bward_factor,
        a.cumulate_fward_factor,
        a.cumulate_bward_factor
      from quotes_window q
      left join adjust_source a
        on a.symbol_norm = q.symbol
       and a.trading_date <= q.snapshot_date
      qualify row_number() over (
        partition by q.symbol, q.snapshot_date
        order by a.trading_date desc, a.source_priority asc
      ) = 1
    ),
    company as (
      select
        case
          when length(regexp_replace(stkcd, '[^0-9]', '', 'g')) = 0
            then null
          else lpad(regexp_replace(stkcd, '[^0-9]', '', 'g'), 6, '0')
        end as symbol_norm,
        indnme,
        markettype,
        province,
        city
      from trd_co
    )
    select
      q.snapshot_date,
      q.symbol,
      q.short_name,
      t.securityid,
      q.open_price,
      q.close_price,
      q.high_price,
      q.low_price,
      q.volume,
      q.amount,
      q.avg_price,
      q.change_ratio,
      q.turnover_rate1,
      q.market_value,
      q.circulated_market_value,
      q.total_share,
      q.circulated_share,
      q.a_circulated_share,
      q.b_circulated_share,
      q.a_value,
      q.b_value,
      v.pe_ratio_1,
      v.pe_ratio_2,
      v.pe_ratio_ttm,
      v.pb_ratio,
      v.pb_ratio_parent,
      v.quarter,
      t.continued_rise_days,
      t.continued_fall_days,
      t.life_high,
      t.life_low,
      t.life_high_week,
      t.life_high_month,
      t.life_high_3month,
      t.life_high_6month,
      t.life_high_one_year,
      t.life_low_week,
      t.life_low_month,
      t.life_low_3month,
      t.life_low_6month,
      t.life_low_one_year,
      a.fward_factor,
      a.bward_factor,
      a.cumulate_fward_factor,
      a.cumulate_bward_factor,
      q.vol_1d,
      q.vol_3d_sum,
      q.vol_3d_up,
      q.vol_3d_trend,
      q.amount_3d_sum,
      q.price_3d_change,
      q.vol_5d_sum,
      q.vol_5d_avg,
      q.vol_5d_up,
      q.amount_5d_sum,
      q.price_5d_change,
      q.return_5d,
      q.return_10d,
      q.ma5,
      q.ma10,
      q.high_5d,
      q.low_5d,
      q.close_above_ma5,
      q.close_above_ma10,
      c.indnme as industry,
      c.markettype,
      c.province,
      c.city
    from quotes_window q
    left join valuation v
      on v.symbol = q.symbol
     and v.snapshot_date = q.snapshot_date
    left join trend t
      on t.symbol_norm = q.symbol
     and t.snapshot_date = q.snapshot_date
    left join adjust a
      on a.symbol = q.symbol
     and a.snapshot_date = q.snapshot_date
    left join company c
      on c.symbol_norm = q.symbol
    where q.snapshot_date >= (select window_start from params)
      and q.snapshot_date <= (select end_date from params)
    order by q.snapshot_date, q.symbol
    """
    rows = con.execute(query, [window_start, start_date, end_date]).fetchdf()
    con.close()
    return rows


def compute_indicators(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    rows = rows.sort_values(["symbol", "snapshot_date"]).reset_index(drop=True)
    rows["snapshot_date"] = pd.to_datetime(rows["snapshot_date"]).dt.date

    def apply_group(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values("snapshot_date").copy()
        group["ma20"] = group["close_price"].rolling(20, min_periods=20).mean()
        close_std_20 = group["close_price"].rolling(
            20, min_periods=20).std(ddof=0)
        group["boll_mid"] = group["ma20"]
        group["boll_upper"] = group["ma20"] + 2 * close_std_20
        group["boll_lower"] = group["ma20"] - 2 * close_std_20

        ema12 = group["close_price"].ewm(span=12, adjust=False).mean()
        ema26 = group["close_price"].ewm(span=26, adjust=False).mean()
        group["macd_dif"] = ema12 - ema26
        group["macd_dea"] = group["macd_dif"].ewm(span=9, adjust=False).mean()
        group["macd_bar"] = (group["macd_dif"] - group["macd_dea"]) * 2

        low_n = group["low_price"].rolling(9, min_periods=9).min()
        high_n = group["high_price"].rolling(9, min_periods=9).max()
        rsv = (group["close_price"] - low_n) / (high_n - low_n) * 100
        k_values = []
        d_values = []
        for value in rsv.values:
            if np.isnan(value):
                k_values.append(np.nan)
                d_values.append(np.nan)
                continue
            prev_k = 50.0 if not k_values or np.isnan(
                k_values[-1]) else k_values[-1]
            prev_d = 50.0 if not d_values or np.isnan(
                d_values[-1]) else d_values[-1]
            k_val = prev_k * 2 / 3 + value / 3
            d_val = prev_d * 2 / 3 + k_val / 3
            k_values.append(k_val)
            d_values.append(d_val)
        group["kdj_k"] = k_values
        group["kdj_d"] = d_values
        group["kdj_j"] = group["kdj_k"] * 3 - group["kdj_d"] * 2

        returns = group["close_price"].pct_change()
        group["volatility_20"] = returns.rolling(
            20, min_periods=20).std(ddof=0)
        return group

    rows = rows.groupby("symbol", group_keys=False).apply(apply_group)
    rows["amount_rank"] = (
        rows.groupby("snapshot_date")["amount"]
        .rank(method="min", ascending=False)
        .astype("Int64")
    )
    return rows


def write_rows(conn, rows: pd.DataFrame, start_date: date, end_date: date) -> int:
    if rows.empty:
        return 0
    rows = compute_indicators(rows)
    rows = rows[
        (rows["snapshot_date"] >= start_date) & (
            rows["snapshot_date"] <= end_date)
    ].copy()
    numeric_round_2 = [
        "open_price",
        "close_price",
        "high_price",
        "low_price",
        "amount",
        "avg_price",
        "change_ratio",
        "turnover_rate1",
        "market_value",
        "circulated_market_value",
        "a_value",
        "b_value",
        "life_high",
        "life_low",
        "life_high_week",
        "life_high_month",
        "life_high_3month",
        "life_high_6month",
        "life_high_one_year",
        "life_low_week",
        "life_low_month",
        "life_low_3month",
        "life_low_6month",
        "life_low_one_year",
        "fward_factor",
        "bward_factor",
        "cumulate_fward_factor",
        "cumulate_bward_factor",
        "amount_3d_sum",
        "price_3d_change",
        "vol_5d_avg",
        "amount_5d_sum",
        "price_5d_change",
        "return_5d",
        "return_10d",
        "ma5",
        "ma10",
        "ma20",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "macd_dif",
        "macd_dea",
        "macd_bar",
        "kdj_k",
        "kdj_d",
        "kdj_j",
        "volatility_20",
        "high_5d",
        "low_5d",
    ]
    for col in numeric_round_2:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").round(2)
    pe_pb_int = [
        "pe_ratio_1",
        "pe_ratio_2",
        "pe_ratio_ttm",
        "pb_ratio",
        "pb_ratio_parent",
    ]
    for col in pe_pb_int:
        if col in rows.columns:
            rows[col] = (
<<<<<<< HEAD
                pd.to_numeric(rows[col], errors="coerce").round(0).astype("Int64")
=======
                pd.to_numeric(rows[col], errors="coerce").round(
                    0).astype("Int64")
>>>>>>> refactor/service-cleanup
            )
    bigint_columns = [
        "volume",
        "total_share",
        "circulated_share",
        "a_circulated_share",
        "b_circulated_share",
        "vol_1d",
        "vol_3d_sum",
        "vol_5d_sum",
        "amount_rank",
    ]
    for col in bigint_columns:
        if col in rows.columns:
            rows[col] = (
<<<<<<< HEAD
                pd.to_numeric(rows[col], errors="coerce").round().astype("Int64")
=======
                pd.to_numeric(
                    rows[col], errors="coerce").round().astype("Int64")
>>>>>>> refactor/service-cleanup
            )
    rows = rows.astype(object).where(pd.notnull(rows), None)
    columns = [
        "snapshot_date",
        "symbol",
        "short_name",
        "securityid",
        "open_price",
        "close_price",
        "high_price",
        "low_price",
        "volume",
        "amount",
        "avg_price",
        "change_ratio",
        "turnover_rate1",
        "market_value",
        "circulated_market_value",
        "total_share",
        "circulated_share",
        "a_circulated_share",
        "b_circulated_share",
        "a_value",
        "b_value",
        "pe_ratio_1",
        "pe_ratio_2",
        "pe_ratio_ttm",
        "pb_ratio",
        "pb_ratio_parent",
        "quarter",
        "continued_rise_days",
        "continued_fall_days",
        "life_high",
        "life_low",
        "life_high_week",
        "life_high_month",
        "life_high_3month",
        "life_high_6month",
        "life_high_one_year",
        "life_low_week",
        "life_low_month",
        "life_low_3month",
        "life_low_6month",
        "life_low_one_year",
        "fward_factor",
        "bward_factor",
        "cumulate_fward_factor",
        "cumulate_bward_factor",
        "vol_1d",
        "vol_3d_sum",
        "vol_3d_up",
        "vol_3d_trend",
        "amount_3d_sum",
        "price_3d_change",
        "vol_5d_sum",
        "vol_5d_avg",
        "vol_5d_up",
        "amount_5d_sum",
        "price_5d_change",
        "return_5d",
        "return_10d",
        "ma5",
        "ma10",
        "ma20",
        "boll_mid",
        "boll_upper",
        "boll_lower",
        "macd_dif",
        "macd_dea",
        "macd_bar",
        "kdj_k",
        "kdj_d",
        "kdj_j",
        "volatility_20",
        "amount_rank",
        "high_5d",
        "low_5d",
        "close_above_ma5",
        "close_above_ma10",
        "industry",
        "markettype",
        "province",
        "city",
    ]
    with conn.cursor() as cur:
        cur.execute(
            "delete from stock_screener_snapshot where snapshot_date >= %s and snapshot_date <= %s",
            (start_date, end_date),
        )
        cur.execute(
            "delete from stock_screener_snapshot where snapshot_date < %s",
            (start_date,),
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerows(rows[columns].itertuples(index=False, name=None))
        buffer.seek(0)
        copy_sql = (
            "copy stock_screener_snapshot ("
            + ", ".join(columns)
            + ") from stdin with (format csv)"
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

    window_start, start_date, end_date = get_dates(args.as_of_date, args.days)
    schema_path = Path(__file__).with_name("stock_screener_snapshot.sql")

    with get_pg_conn() as conn:
        ensure_schema(conn, schema_path)
        rows = fetch_rows(duckdb_path, window_start, start_date, end_date)
        inserted = write_rows(conn, rows, start_date, end_date)

    print(
        "Loaded stock_screener_snapshot rows:",
        inserted,
        "range:",
        start_date,
        "to",
        end_date,
    )


if __name__ == "__main__":
    main()
