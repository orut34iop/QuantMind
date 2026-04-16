#!/usr/bin/env python3
"""
从 db/csmar_data.duckdb 提取可训练特征并写入 Qlib day.bin。

默认策略：
1) 以 TRD_Dalyr 作为日频主表；
2) 对存在重复的高频表先做去重/聚合（HF_VPIN/HF_StockJump/HF_BSImbalance）；
3) 对季频/事件表使用 asof join（仅使用 t 时点可得信息）；
4) 仅增量写入“新增特征文件”，不清理已有 qlib features。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import duckdb
import numpy as np
import pandas as pd


P0_FEATURES = [
    "mktcap_float",
    "mktcap_total",
    "preclose",
    "limit_down",
    "limit_up",
    "limit_status",
    "trade_status",
    "dret_nd",
    "tover_tl",
    "turnover_rate1",
    "mv_total",
    "mv_float",
    "total_share",
    "circ_share",
]

P1_FEATURES = [
    "rrv",
    "rjv",
    "sjv",
    "rs_n",
    "rs_p",
    "is_jump",
    "qsp_time",
    "esp_time",
    "qsp_volume",
    "esp_volume",
    "b_num",
    "s_num",
    "b_volume",
    "s_volume",
    "vpin50",
    "vpin50_volume",
    "life_high_week",
    "life_low_week",
    "life_high_3m",
    "life_low_3m",
    "life_high_1y",
    "life_low_1y",
]

P2_FEATURES = [
    "ps_ttm",
    "tobin_q_a",
    "ev_ebitda_ttm",
    "float_ratio",
    "limited_ratio",
    "nshrttl",
    "nshra",
    "nshrrot",
]

LGBM64_FEATURES = [
    "f_turn",
    "f_smb",
    "f_hml",
    "f_rp",
    "f_b_n",
    "f_s_n",
    "f_b_a_l",
    "f_s_a_l",
    "f_b_a_b",
    "f_s_a_b",
    "f_b_a_s",
    "f_s_a_s",
    "f_qsp",
    "f_esp",
    "f_aqsp",
    "f_vpin",
    "f_rv",
    "f_bv",
    "f_alpha",
    "f_rs_n",
    "f_rs_p",
    "f_rskew",
    "f_rkurt",
    "f_pe",
    "f_pb",
    "f_ev_eb",
    "f_crd",
    "f_cfd",
    "f_daily_return",
    "f_close_price_base",
    "f_vpin_base",
    "f_b_num_l",
    "f_s_num_l",
    "f_b_volume_l",
    "f_s_volume_l",
    "f_b_amount_l",
    "f_s_amount_l",
    "f_b_num_s",
    "f_s_num_s",
    "f_b_amount_s",
    "f_s_amount_s",
    "f_qsp_time",
    "f_esp_time",
    "f_qsp_volume",
    "f_esp_volume",
    "f_qsp_amount",
    "f_esp_amount",
    "f_vpin_volume",
    "f_vpin_n",
    "f_z_adj",
    "f_isjump",
    "f_rjv",
    "f_sjv",
    "f_rrv",
    "f_pe_1",
    "f_ps_ttm",
    "f_pcf_ttm",
    "f_tobin_q",
    "f_cont_lrgvol",
    "f_cont_shrink",
    "f_open",
    "f_high",
    "f_low",
    "f_tover_os",
]


@dataclass(frozen=True)
class ExportConfig:
    db_path: Path
    qlib_dir: Path
    start_date: str
    end_date: str
    pack: str
    limit_symbols: int
    dry_run: bool


def _parse_args() -> ExportConfig:
    parser = argparse.ArgumentParser(description="Export CSMAR feature packs to Qlib .day.bin")
    parser.add_argument("--db-path", default="db/csmar_data.duckdb")
    parser.add_argument("--qlib-dir", default="db/qlib_data")
    parser.add_argument("--start-date", default="2016-01-04")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument(
        "--pack",
        choices=["p0", "p1", "p2", "all", "lgbm64"],
        default="all",
        help="选择导出字段包",
    )
    parser.add_argument(
        "--limit-symbols",
        type=int,
        default=0,
        help="仅导出前N个股票（用于快速验证）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅抽取并打印统计，不写 bin 文件")
    args = parser.parse_args()
    return ExportConfig(
        db_path=Path(args.db_path),
        qlib_dir=Path(args.qlib_dir),
        start_date=args.start_date,
        end_date=args.end_date,
        pack=args.pack,
        limit_symbols=max(0, int(args.limit_symbols)),
        dry_run=bool(args.dry_run),
    )


def _selected_features(pack: str) -> List[str]:
    if pack == "p0":
        return list(P0_FEATURES)
    if pack == "p1":
        return list(P1_FEATURES)
    if pack == "p2":
        return list(P2_FEATURES)
    if pack == "lgbm64":
        return list(LGBM64_FEATURES)
    return list(P0_FEATURES + P1_FEATURES + P2_FEATURES)


def _infer_symbol(stkcd: str) -> str:
    code = str(stkcd or "").strip()
    if len(code) != 6 or not code.isdigit():
        return code.upper()
    if code.startswith(("6", "9")):
        return f"SH{code}"
    if code.startswith(("0", "2", "3")):
        return f"SZ{code}"
    if code.startswith(("4", "8")):
        return f"BJ{code}"
    return code.upper()


def _load_calendar(qlib_dir: Path, start_date: str, end_date: str) -> pd.DatetimeIndex:
    cal_path = qlib_dir / "calendars" / "day.txt"
    if not cal_path.exists():
        raise FileNotFoundError(f"Qlib calendar not found: {cal_path}")
    cal = pd.read_csv(cal_path, header=None, names=["date"])
    cal["date"] = pd.to_datetime(cal["date"])
    scoped = cal[(cal["date"] >= pd.Timestamp(start_date)) & (cal["date"] <= pd.Timestamp(end_date))]
    if scoped.empty:
        raise RuntimeError("calendar 范围为空，请检查 start/end 或 qlib calendar")
    # NOTE:
    # Keep full calendar for start_idx alignment in .day.bin.
    # start_idx must be relative to the full day.txt calendar, not a sliced window.
    return pd.DatetimeIndex(cal["date"].tolist())


def _prepare_feature_table(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> None:
    sql = f"""
    CREATE OR REPLACE TEMP TABLE csmar_feature_pack AS
    WITH dalyr AS (
        SELECT
            stkcd,
            date::DATE AS date,
            Dsmvosd AS mktcap_float,
            Dsmvtll AS mktcap_total,
            PreClosePrice AS preclose,
            LimitDown AS limit_down,
            LimitUp AS limit_up,
            LimitStatus AS limit_status,
            Trdsta AS trade_status,
            Dretnd AS dret_nd
        FROM TRD_Dalyr
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY stkcd, date
            ORDER BY COALESCE(Capchgdt, date) DESC
        ) = 1
    ),
    liq AS (
        SELECT stkcd, date::DATE AS date, ToverTl AS tover_tl
        FROM LIQ_TOVER_D
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
    ),
    bq AS (
        SELECT
            stkcd,
            date::DATE AS date,
            TurnoverRate1 AS turnover_rate1,
            MarketValue AS mv_total,
            CirculatedMarketValue AS mv_float,
            TotalShare AS total_share,
            CirculatedShare AS circ_share
        FROM TRD_BwardQuotation
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY stkcd, date ORDER BY Filling DESC) = 1
    ),
    sr AS (
        SELECT stkcd, date::DATE AS date, RRV AS rrv
        FROM HF_StockRealized
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
    ),
    jump AS (
        SELECT
            stkcd,
            date::DATE AS date,
            RJV AS rjv,
            SJV AS sjv,
            RS_N AS rs_n,
            RS_P AS rs_p,
            ISJump AS is_jump
        FROM HF_StockJump
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
          AND Alpha = 'A'
    ),
    spread AS (
        SELECT
            stkcd,
            date::DATE AS date,
            Qsp_time AS qsp_time,
            Esp_time AS esp_time,
            Qsp_Volume AS qsp_volume,
            Esp_Volume AS esp_volume
        FROM HF_Spread
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
    ),
    bsi AS (
        SELECT
            stkcd,
            date::DATE AS date,
            AVG(B_Num) AS b_num,
            AVG(S_Num) AS s_num,
            AVG(B_Volume) AS b_volume,
            AVG(S_Volume) AS s_volume
        FROM HF_BSImbalance
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY stkcd, date
    ),
    vpin AS (
        SELECT
            stkcd,
            date::DATE AS date,
            VPIN AS vpin50,
            Volume AS vpin50_volume
        FROM HF_VPIN
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
          AND N = 50
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY stkcd, date
            ORDER BY Num_1 DESC
        ) = 1
    ),
    trend AS (
        SELECT
            stkcd,
            date::DATE AS date,
            LifeHighWeek AS life_high_week,
            LifeLowWeek AS life_low_week,
            LifeHigh3Month AS life_high_3m,
            LifeLow3Month AS life_low_3m,
            LifeHighOneYear AS life_high_1y,
            LifeLowOneYear AS life_low_1y
        FROM TRD_StockTrend
        WHERE date BETWEEN '{start_date}' AND '{end_date}'
    ),
    valuation AS (
        SELECT
            stkcd,
            date::DATE AS date,
            ps_ratio_ttm AS ps_ttm,
            tobin_q_a,
            ev_ebitda_ttm
        FROM stk_valuation_raw
        WHERE date <= '{end_date}'
    ),
    shares_evt AS (
        SELECT
            stkcd,
            date::DATE AS date,
            float_ratio,
            limited_ratio
        FROM restricted_shares
        WHERE date <= '{end_date}'
    ),
    capchg AS (
        SELECT
            stkcd,
            date::DATE AS date,
            Nshrttl AS nshrttl,
            Nshra AS nshra,
            Nshrrot AS nshrrot
        FROM TRD_Capchg
        WHERE date <= '{end_date}'
    )
    SELECT
        d.*,
        liq.tover_tl,
        bq.turnover_rate1,
        bq.mv_total,
        bq.mv_float,
        bq.total_share,
        bq.circ_share,
        sr.rrv,
        jump.rjv,
        jump.sjv,
        jump.rs_n,
        jump.rs_p,
        jump.is_jump,
        spread.qsp_time,
        spread.esp_time,
        spread.qsp_volume,
        spread.esp_volume,
        bsi.b_num,
        bsi.s_num,
        bsi.b_volume,
        bsi.s_volume,
        vpin.vpin50,
        vpin.vpin50_volume,
        trend.life_high_week,
        trend.life_low_week,
        trend.life_high_3m,
        trend.life_low_3m,
        trend.life_high_1y,
        trend.life_low_1y,
        v.ps_ttm,
        v.tobin_q_a,
        v.ev_ebitda_ttm,
        rs.float_ratio,
        rs.limited_ratio,
        c.nshrttl,
        c.nshra,
        c.nshrrot
    FROM dalyr d
    LEFT JOIN liq ON d.stkcd = liq.stkcd AND d.date = liq.date
    LEFT JOIN bq ON d.stkcd = bq.stkcd AND d.date = bq.date
    LEFT JOIN sr ON d.stkcd = sr.stkcd AND d.date = sr.date
    LEFT JOIN jump ON d.stkcd = jump.stkcd AND d.date = jump.date
    LEFT JOIN spread ON d.stkcd = spread.stkcd AND d.date = spread.date
    LEFT JOIN bsi ON d.stkcd = bsi.stkcd AND d.date = bsi.date
    LEFT JOIN vpin ON d.stkcd = vpin.stkcd AND d.date = vpin.date
    LEFT JOIN trend ON d.stkcd = trend.stkcd AND d.date = trend.date
    ASOF LEFT JOIN valuation v ON d.stkcd = v.stkcd AND d.date >= v.date
    ASOF LEFT JOIN shares_evt rs ON d.stkcd = rs.stkcd AND d.date >= rs.date
    ASOF LEFT JOIN capchg c ON d.stkcd = c.stkcd AND d.date >= c.date
    """
    con.execute(sql)


def _prepare_lgbm64_feature_table(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> None:
    # Reuse the exact feature engineering SQL from training pipeline to keep online/offline aligned.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from scripts.train_custom_lgbm_duckdb import _sql as _lgbm64_sql

    cols = ", ".join(LGBM64_FEATURES)

    # Build in yearly chunks to avoid OOM on full-range materialization.
    con.execute("DROP TABLE IF EXISTS csmar_feature_pack")
    con.execute(
        f"""
    CREATE OR REPLACE TEMP TABLE csmar_feature_pack AS
    SELECT
        CAST(NULL AS VARCHAR) AS stkcd,
        CAST(NULL AS DATE) AS date,
        {", ".join([f"CAST(NULL AS DOUBLE) AS {c}" for c in LGBM64_FEATURES])}
    WHERE 1 = 0
    """
    )

    s = pd.Timestamp(start_date)
    e = pd.Timestamp(end_date)
    for year in range(s.year, e.year + 1):
        ys = max(pd.Timestamp(f"{year}-01-01"), s)
        ye = min(pd.Timestamp(f"{year}-12-31"), e)
        qs = (ys - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        ys_s = ys.strftime("%Y-%m-%d")
        ye_s = ye.strftime("%Y-%m-%d")
        base_sql = _lgbm64_sql(qs, ye_s)
        insert_sql = f"""
        INSERT INTO csmar_feature_pack
        SELECT
            LPAD(CAST(stkcd AS VARCHAR), 6, '0') AS stkcd,
            CAST(date AS DATE) AS date,
            {cols}
        FROM (
            {base_sql}
        ) t
        WHERE CAST(date AS DATE) BETWEEN '{ys_s}' AND '{ye_s}'
          AND label IS NOT NULL
          AND CAST(stkcd AS VARCHAR) NOT LIKE '4%%'
          AND CAST(stkcd AS VARCHAR) NOT LIKE '8%%'
        """
        con.execute(insert_sql)


def _load_symbol_mapping(con: duckdb.DuckDBPyConnection) -> Dict[str, str]:
    rows = con.execute("SELECT stkcd, adjusted_symbol FROM stock_code_mapping").fetchall()
    return {str(k): str(v).upper() for k, v in rows}


def _write_day_bin(path: Path, start_idx: int, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = np.empty(values.size + 1, dtype=np.float32)
    payload[0] = np.float32(start_idx)
    payload[1:] = values.astype(np.float32, copy=False)
    payload.tofile(path)


def _iter_symbols(con: duckdb.DuckDBPyConnection, limit: int) -> List[str]:
    sql = "SELECT DISTINCT stkcd FROM csmar_feature_pack ORDER BY stkcd"
    if limit > 0:
        sql += f" LIMIT {limit}"
    rows = con.execute(sql).fetchall()
    return [str(r[0]) for r in rows]


def _export_bins(
    con: duckdb.DuckDBPyConnection,
    qlib_dir: Path,
    calendar: pd.DatetimeIndex,
    features: Sequence[str],
    symbol_map: Dict[str, str],
    limit_symbols: int,
    dry_run: bool,
) -> Dict[str, int]:
    features_dir = qlib_dir / "features"
    cal_pos = pd.Series(np.arange(len(calendar), dtype=np.int32), index=calendar)
    symbols = _iter_symbols(con, limit_symbols)

    write_files = 0
    skip_symbols = 0
    for i, stkcd in enumerate(symbols, start=1):
        df = con.execute(
            """
            SELECT stkcd, date, {cols}
            FROM csmar_feature_pack
            WHERE stkcd = ?
            ORDER BY date
            """.format(cols=", ".join(features)),
            [stkcd],
        ).fetchdf()
        if df.empty:
            skip_symbols += 1
            continue

        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= calendar[0]) & (df["date"] <= calendar[-1])]
        if df.empty:
            skip_symbols += 1
            continue
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")

        symbol = symbol_map.get(stkcd, _infer_symbol(stkcd)).lower()
        symbol_dir = features_dir / symbol

        min_date = df["date"].min()
        max_date = df["date"].max()
        if min_date not in cal_pos.index or max_date not in cal_pos.index:
            skip_symbols += 1
            continue

        start_idx = int(cal_pos[min_date])
        end_idx = int(cal_pos[max_date])
        full_idx = calendar[start_idx : end_idx + 1]
        frame = (
            df.set_index("date")[list(features)]
            .sort_index()
            .reindex(full_idx)
        )

        if not dry_run:
            for col in features:
                file_path = symbol_dir / f"{col}.day.bin"
                series = pd.to_numeric(frame[col], errors="coerce")
                values = series.to_numpy(dtype=np.float64, na_value=np.nan).astype(np.float32)
                _write_day_bin(file_path, start_idx, values)
                write_files += 1

        if i % 500 == 0:
            print(f"[progress] symbols={i}/{len(symbols)} written_files={write_files}")

    return {
        "symbols_total": len(symbols),
        "symbols_skipped": skip_symbols,
        "files_written": write_files,
    }


def main() -> None:
    cfg = _parse_args()
    if not cfg.db_path.exists():
        raise FileNotFoundError(f"DuckDB not found: {cfg.db_path}")
    if not cfg.qlib_dir.exists():
        raise FileNotFoundError(f"Qlib dir not found: {cfg.qlib_dir}")

    selected = _selected_features(cfg.pack)
    print(f"[config] pack={cfg.pack} features={len(selected)} range={cfg.start_date}..{cfg.end_date}")
    print(f"[config] db={cfg.db_path} qlib={cfg.qlib_dir} dry_run={cfg.dry_run} limit_symbols={cfg.limit_symbols}")

    calendar = _load_calendar(cfg.qlib_dir, cfg.start_date, cfg.end_date)
    print(f"[calendar] days={len(calendar)} min={calendar[0].date()} max={calendar[-1].date()}")

    con = duckdb.connect(str(cfg.db_path), read_only=True)
    if cfg.pack == "lgbm64":
        _prepare_lgbm64_feature_table(con, cfg.start_date, cfg.end_date)
    else:
        _prepare_feature_table(con, cfg.start_date, cfg.end_date)
    symbol_map = _load_symbol_mapping(con)

    totals = con.execute("SELECT COUNT(*) FROM csmar_feature_pack").fetchone()[0]
    uniq = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT stkcd, date FROM csmar_feature_pack)").fetchone()[0]
    print(f"[dataset] rows={totals} uniq(stkcd,date)={uniq} dup={totals-uniq}")

    out = _export_bins(
        con=con,
        qlib_dir=cfg.qlib_dir,
        calendar=calendar,
        features=selected,
        symbol_map=symbol_map,
        limit_symbols=cfg.limit_symbols,
        dry_run=cfg.dry_run,
    )
    out["features_selected"] = len(selected)
    out["pack"] = cfg.pack
    out["date_range"] = [cfg.start_date, cfg.end_date]
    print("[done]", json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
