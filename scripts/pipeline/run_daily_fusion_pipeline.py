#!/usr/bin/env python3
"""
一键执行日频双模型融合流程：
1) 从 Qlib 读取当日 LGBM 64D 截面特征
2) 从 Qlib 读取最近 N 日 TFT 序列特征
3) 调用 engine /api/v1/pipeline/runs
4) 轮询任务并落盘结果摘要
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from urllib import error, request

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROVIDER_URI = PROJECT_ROOT / "db" / "qlib_data"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models" / "production"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "fusion_runs"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _http_json(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    payload: Dict[str, Any] | None = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    data = None
    req_headers = dict(headers)
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url=url, method=method.upper(), headers=req_headers, data=data)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc


def _resolve_trade_date(calendar: Sequence[pd.Timestamp], trade_date: str | None) -> pd.Timestamp:
    if not calendar:
        raise ValueError("qlib calendar is empty")
    if trade_date:
        t = pd.Timestamp(trade_date).normalize()
        if t not in set(calendar):
            raise ValueError(f"trade_date={trade_date} not found in qlib calendar")
        return t
    return pd.Timestamp(calendar[-1]).normalize()


def _resolve_latest_feature_date(
    *,
    D: Any,
    calendar: Sequence[pd.Timestamp],
    instruments_def: Any,
    probe_field: str,
    lookback_days: int = 30,
) -> pd.Timestamp:
    cal = [pd.Timestamp(x).normalize() for x in calendar]
    candidates = cal[-lookback_days:] if len(cal) > lookback_days else cal
    for dt in reversed(candidates):
        inst = D.list_instruments(
            instruments_def,
            start_time=dt.strftime("%Y-%m-%d"),
            end_time=dt.strftime("%Y-%m-%d"),
            as_list=True,
        )
        if not inst:
            continue
        probe = inst[: min(50, len(inst))]
        df = D.features(
            probe,
            [f"${probe_field}"],
            start_time=dt.strftime("%Y-%m-%d"),
            end_time=dt.strftime("%Y-%m-%d"),
        )
        if df is not None and not df.empty:
            return dt
    raise ValueError(
        f"no available feature data found in recent {len(candidates)} calendar days"
    )


def _calendar_window_start(
    calendar: Sequence[pd.Timestamp], trade_date: pd.Timestamp, lookback: int
) -> pd.Timestamp:
    cal_list = list(calendar)
    idx = cal_list.index(trade_date)
    start_idx = max(0, idx - lookback + 1)
    return pd.Timestamp(cal_list[start_idx]).normalize()


def _normalize_feature_frame(df: pd.DataFrame, feature_cols: List[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["instrument", "datetime", *feature_cols])

    out = df.copy()
    if isinstance(out.index, pd.MultiIndex):
        out = out.reset_index()
    else:
        out = out.reset_index(drop=False)

    if "instrument" not in out.columns:
        for c in ("level_0", "index"):
            if c in out.columns:
                out = out.rename(columns={c: "instrument"})
                break
    if "datetime" not in out.columns:
        for c in ("date", "level_1"):
            if c in out.columns:
                out = out.rename(columns={c: "datetime"})
                break
    if "instrument" not in out.columns or "datetime" not in out.columns:
        raise ValueError("unexpected qlib frame: missing instrument/datetime columns")

    rename_map = {}
    for c in out.columns:
        if isinstance(c, str) and c.startswith("$"):
            rename_map[c] = c[1:]
    if rename_map:
        out = out.rename(columns=rename_map)

    missing = [c for c in feature_cols if c not in out.columns]
    if missing:
        for c in missing:
            out[c] = np.nan

    out["datetime"] = pd.to_datetime(out["datetime"]).dt.normalize()
    out["instrument"] = out["instrument"].astype(str)
    return out[["instrument", "datetime", *feature_cols]]


def _build_lgbm_rows(
    *,
    D: Any,
    instruments: Any,
    trade_date: pd.Timestamp,
    feature_cols: List[str],
) -> Dict[str, Dict[str, Any]]:
    exprs = [f"${c}" for c in feature_cols]
    df = D.features(
        instruments,
        exprs,
        start_time=trade_date.strftime("%Y-%m-%d"),
        end_time=trade_date.strftime("%Y-%m-%d"),
    )
    norm = _normalize_feature_frame(df, feature_cols)
    norm = norm[norm["datetime"] == trade_date]
    if norm.empty:
        raise ValueError(f"no lgbm features found on {trade_date.date()}")

    rows: Dict[str, Dict[str, Any]] = {}
    for _, r in norm.iterrows():
        symbol = str(r["instrument"])
        item = {
            "symbol": symbol,
            "instrument": symbol,
            "date": trade_date.strftime("%Y-%m-%d"),
        }
        for c in feature_cols:
            v = r[c]
            item[c] = float(v) if pd.notna(v) else 0.0
        if "f_close_price_base" in feature_cols:
            item["close"] = float(item["f_close_price_base"])
        rows[symbol] = item
    return rows


def _build_tft_sequences(
    *,
    D: Any,
    instruments: Any,
    start_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    feature_cols: List[str],
    lookback: int,
) -> Tuple[List[str], List[List[List[float]]]]:
    exprs = [f"${c}" for c in feature_cols]
    df = D.features(
        instruments,
        exprs,
        start_time=start_date.strftime("%Y-%m-%d"),
        end_time=trade_date.strftime("%Y-%m-%d"),
    )
    norm = _normalize_feature_frame(df, feature_cols)
    if norm.empty:
        return [], []

    symbols: List[str] = []
    sequences: List[List[List[float]]] = []
    grouped = norm.groupby("instrument", sort=False)
    for inst, g in grouped:
        g2 = g.sort_values("datetime")
        if g2["datetime"].iloc[-1] != trade_date:
            continue
        if len(g2) < lookback:
            continue
        tail = g2.tail(lookback).copy()
        feat = tail[feature_cols].ffill().bfill().fillna(0.0).to_numpy(dtype=np.float32)
        symbols.append(str(inst))
        sequences.append(feat.tolist())
    return symbols, sequences


def _poll_pipeline(
    *,
    api_base: str,
    run_id: str,
    headers: Dict[str, str],
    interval: float,
    timeout_seconds: int,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while True:
        status = _http_json("GET", f"{api_base}/runs/{run_id}", headers=headers, timeout=30)
        state = str(status.get("status", "")).lower()
        stage = status.get("stage")
        print(f"[poll] run_id={run_id} status={state} stage={stage}")
        if state in {"completed", "failed"}:
            return status
        if time.time() > deadline:
            raise TimeoutError(f"pipeline run timeout after {timeout_seconds}s")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily LGBM+TFT fusion pipeline")
    parser.add_argument("--provider-uri", default=str(DEFAULT_PROVIDER_URI))
    parser.add_argument("--models-dir", default=str(DEFAULT_MODELS_DIR))
    parser.add_argument("--api-base", default="http://127.0.0.1:8001/api/v1/pipeline")
    parser.add_argument("--trade-date", default=None, help="YYYY-MM-DD, default latest qlib date")
    parser.add_argument("--market", default="all", help="qlib instruments market, default=all")
    parser.add_argument("--limit-symbols", type=int, default=0, help="0 means no limit")
    parser.add_argument("--model-id", default="model_qlib")
    parser.add_argument("--tft-model-id", default="tft_native")
    parser.add_argument("--user-id", default="system")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--internal-secret", default=os.getenv("INTERNAL_CALL_SECRET", "dev-internal-call-secret"))
    parser.add_argument("--topk", type=int, default=50)
    parser.add_argument("--n-drop", type=int, default=5)
    parser.add_argument("--start-date", default=None, help="backtest start date, default trade_date")
    parser.add_argument("--end-date", default=None, help="backtest end date, default trade_date")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-bj", action="store_true", help="include BJ instruments (default: excluded)")
    args = parser.parse_args()

    import qlib
    from qlib.config import C
    from qlib.data import D

    qlib.init(provider_uri=args.provider_uri, region="cn")
    C["kernels"] = 1
    C["joblib_backend"] = "threading"

    calendar = [pd.Timestamp(x).normalize() for x in D.calendar()]
    trade_date = _resolve_trade_date(calendar, args.trade_date)

    models_dir = Path(args.models_dir)
    lgbm_meta = _load_json(models_dir / "model_qlib" / "metadata.json")
    tft_meta = _load_json(models_dir / "tft_native" / "inference_metadata.json")
    lgbm_features = [str(c) for c in lgbm_meta.get("feature_columns", [])]
    tft_features = [str(c) for c in (tft_meta.get("input_spec", {}) or {}).get("feature_columns", [])]
    tft_lookback = int((tft_meta.get("preprocess", {}) or {}).get("lookback_window") or 30)

    if not lgbm_features:
        raise ValueError("model_qlib metadata missing feature_columns")
    if not tft_features:
        raise ValueError("tft_native inference_metadata missing input_spec.feature_columns")

    instruments_def = D.instruments(market=args.market)

    if args.trade_date is None:
        trade_date = _resolve_latest_feature_date(
            D=D,
            calendar=calendar,
            instruments_def=instruments_def,
            probe_field=lgbm_features[0],
            lookback_days=30,
        )
    active_instruments = D.list_instruments(
        instruments_def,
        start_time=trade_date.strftime("%Y-%m-%d"),
        end_time=trade_date.strftime("%Y-%m-%d"),
        as_list=True,
    )
    if args.limit_symbols and args.limit_symbols > 0:
        active_instruments = active_instruments[: args.limit_symbols]
    if not active_instruments:
        raise ValueError(
            f"no active instruments for market={args.market} on {trade_date.date()}"
        )

    lgbm_rows_map = _build_lgbm_rows(
        D=D, instruments=active_instruments, trade_date=trade_date, feature_cols=lgbm_features
    )

    tft_start = _calendar_window_start(calendar, trade_date, tft_lookback)
    tft_symbols, tft_sequences = _build_tft_sequences(
        D=D,
        instruments=active_instruments,
        start_date=tft_start,
        trade_date=trade_date,
        feature_cols=tft_features,
        lookback=tft_lookback,
    )

    tft_map = {sym: seq for sym, seq in zip(tft_symbols, tft_sequences)}
    common_symbols = [s for s in tft_symbols if s in lgbm_rows_map]
    if not args.include_bj:
        common_symbols = [s for s in common_symbols if not str(s).upper().startswith("BJ")]
    if not common_symbols:
        raise ValueError("no overlapping symbols between lgbm snapshot and tft sequences")

    lgbm_rows = [lgbm_rows_map[s] for s in common_symbols]
    tft_payload = {
        "symbols": common_symbols,
        "sequences": [tft_map[s] for s in common_symbols],
    }

    start_date = args.start_date or trade_date.strftime("%Y-%m-%d")
    end_date = args.end_date or trade_date.strftime("%Y-%m-%d")
    payload = {
        "prompt": f"daily_fusion_signal_{trade_date.strftime('%Y%m%d')}",
        "user_id": args.user_id,
        "tenant_id": args.tenant_id,
        "inference_enabled": True,
        "model_id": args.model_id,
        "inference_data": lgbm_rows,
        "tft_model_id": args.tft_model_id,
        "tft_inference_data": tft_payload,
        "start_date": start_date,
        "end_date": end_date,
        "benchmark": "SH000300",
        "universe": "all",
        "topk": args.topk,
        "n_drop": args.n_drop,
    }

    print(
        "[payload] "
        f"trade_date={trade_date.date()} symbols={len(common_symbols)} "
        f"lgbm_features={len(lgbm_features)} tft_features={len(tft_features)} lookback={tft_lookback}"
    )

    if args.dry_run:
        print("[dry-run] payload prepared, skip api call")
        return

    headers = {
        "X-Internal-Call": args.internal_secret,
        "X-User-Id": args.user_id,
        "X-Tenant-Id": args.tenant_id,
    }
    create_resp = _http_json(
        "POST",
        f"{args.api_base}/runs",
        headers=headers,
        payload=payload,
        timeout=120,
    )
    run_id = str(create_resp.get("run_id") or "")
    if not run_id:
        raise RuntimeError(f"pipeline create response missing run_id: {create_resp}")
    print(f"[create] run_id={run_id}")

    final_status = _poll_pipeline(
        api_base=args.api_base,
        run_id=run_id,
        headers=headers,
        interval=args.poll_interval,
        timeout_seconds=args.timeout_seconds,
    )

    result = _http_json(
        "GET",
        f"{args.api_base}/runs/{run_id}/result",
        headers=headers,
        timeout=60,
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"fusion_run_{trade_date.strftime('%Y%m%d')}_{run_id}.json"
    summary = {
        "trade_date": trade_date.strftime("%Y-%m-%d"),
        "run_id": run_id,
        "final_status": final_status,
        "result": result,
    }
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] status={final_status.get('status')} stage={final_status.get('stage')}")
    print(f"[done] result_file={out_file}")


if __name__ == "__main__":
    main()
