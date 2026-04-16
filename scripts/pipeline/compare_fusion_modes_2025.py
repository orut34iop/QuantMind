#!/usr/bin/env python3
"""
对比两种融合模式在 2025 区间的回测表现：
1) baseline_weighted_300_100_50（旧口径）
2) cascade_tft_top500_to_50（LGBM先500，再TFT选50）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.engine.qlib_app.schemas.backtest import (
    QlibBacktestRequest,
    QlibStrategyParams,
)
from backend.services.engine.qlib_app.services.backtest_service import QlibBacktestService

LGBM_PRED_DEFAULT = PROJECT_ROOT / "models" / "production" / "model_qlib" / "pred_test_2025.pkl"
TFT_PRED_DEFAULT = (
    PROJECT_ROOT / "models" / "model_preview" / "production" / "tft_native_v1" / "pred_2025.pkl"
)
OUTPUT_DIR_DEFAULT = PROJECT_ROOT / "backtest_results" / "fusion_compare_2025"


@dataclass
class FusionBuildResult:
    name: str
    pred_path: Path
    signal_count: int
    date_range: Tuple[str, str]


def _to_qlib_symbol(code: str) -> str:
    c = str(code).strip()
    if len(c) == 6 and c.isdigit():
        if c.startswith(("5", "6", "9")):
            return f"SH{c}"
        if c.startswith("8"):
            return f"BJ{c}"
        return f"SZ{c}"
    return c.upper()


def _exclude_bj(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    inst = df.index.get_level_values("instrument").astype(str)
    mask = ~inst.str.upper().str.startswith("BJ")
    return df[mask]


def _load_lgbm_pred(path: Path) -> pd.DataFrame:
    df = pd.read_pickle(path)
    if isinstance(df, pd.Series):
        df = df.to_frame("score")
    if not isinstance(df.index, pd.MultiIndex):
        raise ValueError("lgbm pred must have MultiIndex(datetime, instrument)")
    out = df.copy()
    out.index = out.index.set_names(["datetime", "instrument"])
    out = out.rename(columns={out.columns[0]: "lgbm_score"}) if "lgbm_score" not in out.columns else out
    return out[["lgbm_score"]].sort_index()


def _load_tft_pred(path: Path) -> pd.DataFrame:
    raw = pd.read_pickle(path)
    if raw.empty:
        raise ValueError("tft pred is empty")
    if {"stkcd", "date", "score"} - set(raw.columns):
        raise ValueError("tft pred must include stkcd/date/score columns")
    out = raw[["stkcd", "date", "score"]].copy()
    out["instrument"] = out["stkcd"].map(_to_qlib_symbol)
    out["datetime"] = pd.to_datetime(out["date"]).dt.normalize()
    out["tft_score"] = pd.to_numeric(out["score"], errors="coerce")
    out = out.dropna(subset=["tft_score"])
    out = out[["datetime", "instrument", "tft_score"]].drop_duplicates(
        subset=["datetime", "instrument"], keep="last"
    )
    return out.set_index(["datetime", "instrument"]).sort_index()


def _rank_desc(s: pd.Series) -> pd.Series:
    return s.rank(method="average", ascending=False, pct=True)


def _build_daily_signals(
    lgbm: pd.DataFrame,
    tft: pd.DataFrame,
    *,
    mode: str,
) -> pd.DataFrame:
    joined = lgbm.join(tft, how="left")
    rows: List[pd.DataFrame] = []
    for dt, day in joined.groupby(level="datetime", sort=True):
        day2 = day.droplevel("datetime").copy()
        day2 = day2.sort_values("lgbm_score", ascending=False)
        if mode == "baseline":
            # 旧口径：LGBM top300 -> prefilter100 -> weighted(0.65/0.35) top50
            cand = day2.head(300).head(100).copy()
            l_rank = _rank_desc(cand["lgbm_score"])
            t_rank = _rank_desc(cand["tft_score"].fillna(cand["lgbm_score"]))
            cand["score"] = 0.65 * l_rank + 0.35 * t_rank
            sel = cand.sort_values("score", ascending=False).head(50)
        elif mode == "cascade":
            # 新口径：LGBM top500 -> TFT score top50（reject fallback）
            cand = day2.head(500).copy()
            cand = cand[cand["tft_score"].notna()]
            if cand.empty:
                continue
            sel = cand.sort_values("tft_score", ascending=False).head(50).copy()
            sel["score"] = sel["tft_score"].astype(float)
        else:
            raise ValueError(f"unknown mode: {mode}")

        if sel.empty:
            continue
        sel = sel[["score"]].copy()
        sel.index.name = "instrument"
        sel["datetime"] = dt
        sel = sel.reset_index().set_index(["datetime", "instrument"]).sort_index()
        rows.append(sel)

    if not rows:
        raise ValueError(f"no signals generated for mode={mode}")
    return pd.concat(rows).sort_index()


def _save_pred(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)


async def _run_backtest(
    *,
    service: QlibBacktestService,
    signal_path: Path,
    start_date: str,
    end_date: str,
    benchmark: str,
    user_id: str,
    tenant_id: str,
    deal_price: str,
) -> Dict:
    req = QlibBacktestRequest(
        strategy_type="TopkDropout",
        strategy_params=QlibStrategyParams(
            topk=50,
            n_drop=5,
            signal=str(signal_path.resolve()),
        ),
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        universe="all",
        deal_price=deal_price,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    res = await service.run_backtest(req)
    return res.model_dump()


async def _run_compare(
    *,
    baseline_path: Path,
    cascade_path: Path,
    start_date: str,
    end_date: str,
    benchmark: str,
    user_id: str,
    tenant_id: str,
    deal_price: str,
) -> Tuple[Dict, Dict]:
    service = QlibBacktestService(provider_uri="db/qlib_data", region="cn")
    baseline_res = await _run_backtest(
        service=service,
        signal_path=baseline_path,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        user_id=user_id,
        tenant_id=tenant_id,
        deal_price=deal_price,
    )
    cascade_res = await _run_backtest(
        service=service,
        signal_path=cascade_path,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        user_id=user_id,
        tenant_id=tenant_id,
        deal_price=deal_price,
    )
    return baseline_res, cascade_res


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare fusion modes in 2025")
    parser.add_argument("--lgbm-pred", default=str(LGBM_PRED_DEFAULT))
    parser.add_argument("--tft-pred", default=str(TFT_PRED_DEFAULT))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR_DEFAULT))
    parser.add_argument("--user-id", default="system")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--deal-price", choices=["open", "close"], default="close")
    parser.add_argument("--benchmark", default="SH000300")
    parser.add_argument("--exclude-bj", action="store_true", default=True)
    parser.add_argument("--include-bj", action="store_true", help="override and include BJ instruments")
    args = parser.parse_args()

    lgbm = _load_lgbm_pred(Path(args.lgbm_pred))
    tft = _load_tft_pred(Path(args.tft_pred))
    if args.exclude_bj and not args.include_bj:
        lgbm = _exclude_bj(lgbm)
        tft = _exclude_bj(tft)

    overlap = lgbm.join(tft, how="inner")
    if overlap.empty:
        raise ValueError("no overlap between lgbm and tft predictions")
    start_date = str(overlap.index.get_level_values("datetime").min().date())
    end_date = str(overlap.index.get_level_values("datetime").max().date())

    baseline_pred = _build_daily_signals(lgbm, tft, mode="baseline")
    cascade_pred = _build_daily_signals(lgbm, tft, mode="cascade")

    out_dir = Path(args.output_dir)
    baseline_path = out_dir / "pred_baseline_weighted_300_100_50.pkl"
    cascade_path = out_dir / "pred_cascade_500_to_50.pkl"
    _save_pred(baseline_pred, baseline_path)
    _save_pred(cascade_pred, cascade_path)

    benchmark = str(args.benchmark).strip().upper()
    baseline_res, cascade_res = asyncio.run(
        _run_compare(
            baseline_path=baseline_path,
            cascade_path=cascade_path,
            start_date=start_date,
            end_date=end_date,
            benchmark=benchmark,
            user_id=args.user_id,
            tenant_id=args.tenant_id,
            deal_price=args.deal_price,
        )
    )

    def _pick(res: Dict) -> Dict:
        return {
            "status": res.get("status"),
            "annual_return": res.get("annual_return"),
            "total_return": res.get("total_return"),
            "sharpe_ratio": res.get("sharpe_ratio"),
            "max_drawdown": res.get("max_drawdown"),
            "alpha": res.get("alpha"),
            "win_rate": res.get("win_rate"),
            "total_trades": res.get("total_trades"),
            "backtest_id": res.get("backtest_id"),
            "error_message": res.get("error_message"),
        }

    report = {
        "date_range": [start_date, end_date],
        "deal_price": args.deal_price,
        "benchmark": benchmark,
        "signals": {
            "baseline_days": int(baseline_pred.index.get_level_values("datetime").nunique()),
            "cascade_days": int(cascade_pred.index.get_level_values("datetime").nunique()),
            "baseline_rows": int(len(baseline_pred)),
            "cascade_rows": int(len(cascade_pred)),
        },
        "baseline_weighted_300_100_50": _pick(baseline_res),
        "cascade_tft_500_to_50": _pick(cascade_res),
    }

    out_json = out_dir / "compare_2025_report.json"
    out_md = out_dir / "compare_2025_report.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _fmt(v) -> str:
        if v is None:
            return "NA"
        try:
            return f"{float(v):.6f}"
        except Exception:
            return str(v)

    md = [
        "# 2025 融合模式对比报告",
        "",
        f"- 区间: `{start_date}` ~ `{end_date}`",
        f"- 成交价: `{args.deal_price}`",
        f"- baseline: `LGBM top300 -> prefilter100 -> weighted(0.65/0.35) top50`",
        f"- cascade: `LGBM top500 -> TFT top50`",
        "",
        "## 关键指标",
        "",
        "| 模式 | Annual Return | Total Return | Sharpe | Max Drawdown | Alpha |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| baseline | {_fmt(report['baseline_weighted_300_100_50']['annual_return'])} "
            f"| {_fmt(report['baseline_weighted_300_100_50']['total_return'])} "
            f"| {_fmt(report['baseline_weighted_300_100_50']['sharpe_ratio'])} "
            f"| {_fmt(report['baseline_weighted_300_100_50']['max_drawdown'])} "
            f"| {_fmt(report['baseline_weighted_300_100_50']['alpha'])} |"
        ),
        (
            f"| cascade | {_fmt(report['cascade_tft_500_to_50']['annual_return'])} "
            f"| {_fmt(report['cascade_tft_500_to_50']['total_return'])} "
            f"| {_fmt(report['cascade_tft_500_to_50']['sharpe_ratio'])} "
            f"| {_fmt(report['cascade_tft_500_to_50']['max_drawdown'])} "
            f"| {_fmt(report['cascade_tft_500_to_50']['alpha'])} |"
        ),
        "",
    ]
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[done] report_json={out_json}")
    print(f"[done] report_md={out_md}")


if __name__ == "__main__":
    main()
