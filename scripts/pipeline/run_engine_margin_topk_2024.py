#!/usr/bin/env python3
"""调用后端 quantmind-engine 执行 2024 年多空 TopK 回测。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Any, Dict

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.shared.margin_stock_pool import MarginStockPoolService, normalize_symbol

DEFAULT_ENGINE_URL = "http://127.0.0.1:8001/api/v1/qlib/backtest"
DEFAULT_MARGIN_POOL = PROJECT_ROOT / "db" / "qlib_data" / "instruments" / "margin.txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backtest_results" / "margin_topk_2024"
DEFAULT_PRED_CANDIDATES = [
    PROJECT_ROOT / "models" / "production" / "05_T5_Selected" / "pred.pkl",
    PROJECT_ROOT / "models" / "production" / "alpha158" / "pred.pkl",
]


def _resolve_default_pred() -> Path:
    for candidate in DEFAULT_PRED_CANDIDATES:
        if candidate.exists():
            return candidate
    return DEFAULT_PRED_CANDIDATES[0]


def _load_pred_frame(path: Path) -> pd.DataFrame:
    # 兼容历史 pred.pkl 在旧 numpy 命名空间下序列化的情况。
    sys.modules.setdefault("numpy._core", np.core)
    sys.modules.setdefault("numpy._core.numeric", np.core.numeric)
    pred = pd.read_pickle(path)
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    if not isinstance(pred, pd.DataFrame):
        raise TypeError(f"pred.pkl 类型不支持: {type(pred)!r}")
    if not isinstance(pred.index, pd.MultiIndex):
        raise ValueError("pred.pkl 必须为 MultiIndex(datetime, instrument)")
    out = pred.copy()
    out.index = out.index.set_names(["datetime", "instrument"])
    if "score" not in out.columns:
        out = out.rename(columns={out.columns[0]: "score"})
    return out[["score"]].sort_index()


def _filter_margin_eligible(pred: pd.DataFrame, pool_path: Path) -> pd.DataFrame:
    pool = MarginStockPoolService(pool_path)
    eligible = pool.snapshot().symbols
    instruments = pred.index.get_level_values("instrument").map(normalize_symbol)
    filtered = pred[instruments.isin(eligible)].copy()
    if filtered.empty:
        raise ValueError("过滤两融股票池后信号为空，请检查 pred.pkl 和融资融券清单")
    filtered.index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(filtered.index.get_level_values("datetime")),
            instruments[instruments.isin(eligible)],
        ],
        names=["datetime", "instrument"],
    )
    return filtered.sort_index()


def _build_strategy_content(
    *,
    topk: int,
    short_topk: int,
    long_exposure: float,
    short_exposure: float,
    rebalance_days: int,
) -> str:
    template = Template(
        """
        import pandas as pd
        from qlib.contrib.strategy.signal_strategy import WeightStrategyBase


        class MarginTopKLongShortStrategy(WeightStrategyBase):
            def __init__(
                self,
                topk=50,
                short_topk=50,
                long_exposure=1.0,
                short_exposure=1.0,
                rebalance_days=1,
                enable_short_selling=True,
                **kwargs,
            ):
                self.topk = int(topk)
                self.short_topk = int(short_topk)
                self.long_exposure = float(long_exposure)
                self.short_exposure = float(short_exposure)
                self.rebalance_days = max(1, int(rebalance_days))
                self.enable_short_selling = bool(enable_short_selling)
                super().__init__(**kwargs)

            def generate_target_weight_position(
                self,
                score,
                current,
                trade_start_time,
                trade_end_time,
            ):
                trade_step = self.trade_calendar.get_trade_step()
                if self.rebalance_days > 1 and trade_step % self.rebalance_days != 0:
                    return current.get_stock_weight_dict()

                if score is None:
                    return {}
                if isinstance(score, pd.DataFrame):
                    if "score" in score.columns:
                        score = score["score"]
                    else:
                        score = score.iloc[:, 0]
                score = pd.Series(score).dropna().sort_values(ascending=False)
                if score.empty:
                    return {}

                weights = {}

                longs = score.head(self.topk)
                if len(longs) > 0 and self.long_exposure > 0:
                    long_weight = self.long_exposure / len(longs)
                    for instrument in longs.index:
                        weights[str(instrument)] = float(long_weight)

                if self.enable_short_selling and self.short_topk > 0 and self.short_exposure > 0:
                    shorts = score.tail(self.short_topk)
                    if len(shorts) > 0:
                        short_weight = self.short_exposure / len(shorts)
                        for instrument in shorts.index:
                            inst = str(instrument)
                            if inst in weights:
                                continue
                            weights[inst] = -float(short_weight)

                return weights


        STRATEGY_CONFIG = {
            "class": "MarginTopKLongShortStrategy",
            "module_path": "",
            "kwargs": {
                "signal": "<PRED>",
                "topk": $topk,
                "short_topk": $short_topk,
                "long_exposure": $long_exposure,
                "short_exposure": $short_exposure,
                "rebalance_days": $rebalance_days,
                "enable_short_selling": True,
            },
        }
    """
    )
    return dedent(
        template.substitute(
        topk=int(topk),
        short_topk=int(short_topk),
        long_exposure=float(long_exposure),
        short_exposure=float(short_exposure),
        rebalance_days=int(rebalance_days),
        )
    ).strip()


def _build_payload(
    *,
    pred_path: Path,
    universe_path: Path,
    start_date: str,
    end_date: str,
    topk: int,
    short_topk: int,
    long_exposure: float,
    short_exposure: float,
    benchmark: str,
    deal_price: str,
    rebalance_days: int,
    initial_capital: float,
    user_id: str,
    tenant_id: str,
    margin_stock_pool: str,
    borrow_rate: float,
    financing_rate: float,
    max_short_exposure: float,
    max_leverage: float,
) -> Dict[str, Any]:
    return {
        "strategy_type": "custom",
        "strategy_content": _build_strategy_content(
            topk=topk,
            short_topk=short_topk,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            rebalance_days=rebalance_days,
        ),
        "strategy_params": {
            "signal": str(pred_path.resolve()),
            "topk": topk,
            "rebalance_days": rebalance_days,
            "enable_short_selling": True,
            "margin_stock_pool": margin_stock_pool,
            "borrow_rate": borrow_rate,
            "financing_rate": financing_rate,
            "max_short_exposure": max_short_exposure,
            "max_leverage": max_leverage,
        },
        "start_date": start_date,
        "end_date": end_date,
        "benchmark": benchmark,
        "universe": str(universe_path.resolve()),
        "deal_price": deal_price,
        "initial_capital": initial_capital,
        "user_id": user_id,
        "tenant_id": tenant_id,
    }


def _headers(user_id: str, tenant_id: str) -> Dict[str, str]:
    internal_secret = str(os.getenv("INTERNAL_CALL_SECRET", "")).strip()
    if not internal_secret:
        raise EnvironmentError("缺少 INTERNAL_CALL_SECRET，无法调用后端回测引擎")
    return {
        "Content-Type": "application/json",
        "X-Internal-Call": internal_secret,
        "X-User-Id": str(user_id),
        "X-Tenant-Id": str(tenant_id or "default"),
    }


def _save_outputs(
    *,
    output_dir: Path,
    payload: Dict[str, Any],
    result: Dict[str, Any],
    filtered_pred_path: Path,
    universe_path: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "request_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "backtest_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    summary = {
        "backtest_id": result.get("backtest_id"),
        "status": result.get("status"),
        "total_return": result.get("total_return"),
        "annual_return": result.get("annual_return"),
        "benchmark_return": result.get("benchmark_return"),
        "alpha": result.get("alpha"),
        "sharpe_ratio": result.get("sharpe_ratio"),
        "max_drawdown": result.get("max_drawdown"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "filtered_pred_path": str(filtered_pred_path.resolve()),
        "universe_path": str(universe_path.resolve()),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    equity_curve = result.get("equity_curve") or []
    if equity_curve:
        pd.DataFrame(equity_curve).to_csv(output_dir / "equity_curve.csv", index=False)
    trades = result.get("trades") or []
    if trades:
        pd.DataFrame(trades).to_csv(output_dir / "trades.csv", index=False)
    positions = result.get("positions") or []
    if positions:
        pd.DataFrame(positions).to_csv(output_dir / "positions.csv", index=False)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="调用 quantmind-engine 回测 2024 多空 TopK 策略")
    parser.add_argument("--engine-url", default=DEFAULT_ENGINE_URL)
    parser.add_argument("--pred-path", default=str(_resolve_default_pred()))
    parser.add_argument("--margin-pool-path", default=str(DEFAULT_MARGIN_POOL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--topk", type=int, default=50)
    parser.add_argument("--short-topk", type=int, default=50)
    parser.add_argument("--long-exposure", type=float, default=1.0)
    parser.add_argument("--short-exposure", type=float, default=1.0)
    parser.add_argument("--rebalance-days", type=int, default=1)
    parser.add_argument("--benchmark", default="SH000300")
    parser.add_argument("--deal-price", choices=["open", "close"], default="open")
    parser.add_argument("--initial-capital", type=float, default=100000000)
    parser.add_argument("--user-id", default="system")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--margin-stock-pool", default="fixed")
    parser.add_argument("--universe-path", default=str(DEFAULT_MARGIN_POOL))
    parser.add_argument("--borrow-rate", type=float, default=0.08)
    parser.add_argument("--financing-rate", type=float, default=0.08)
    parser.add_argument("--max-short-exposure", type=float, default=1.0)
    parser.add_argument("--max-leverage", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    pred_path = Path(args.pred_path)
    margin_pool_path = Path(args.margin_pool_path)
    universe_path = Path(args.universe_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pred = _load_pred_frame(pred_path)
    pred = pred.loc[
        (
            pd.to_datetime(pred.index.get_level_values("datetime")) >= pd.Timestamp(args.start_date)
        )
        & (
            pd.to_datetime(pred.index.get_level_values("datetime")) <= pd.Timestamp(args.end_date)
        )
    ]
    if pred.empty:
        raise ValueError("指定日期区间内 pred.pkl 没有信号数据")

    filtered_pred = _filter_margin_eligible(pred, margin_pool_path)
    filtered_pred_path = output_dir / f"{pred_path.stem}_margin_filtered_2024.pkl"
    filtered_pred.to_pickle(filtered_pred_path)

    payload = _build_payload(
        pred_path=filtered_pred_path,
        universe_path=universe_path,
        start_date=args.start_date,
        end_date=args.end_date,
        topk=args.topk,
        short_topk=args.short_topk,
        long_exposure=args.long_exposure,
        short_exposure=args.short_exposure,
        benchmark=args.benchmark,
        deal_price=args.deal_price,
        rebalance_days=args.rebalance_days,
        initial_capital=args.initial_capital,
        user_id=args.user_id,
        tenant_id=args.tenant_id,
        margin_stock_pool=args.margin_stock_pool,
        borrow_rate=args.borrow_rate,
        financing_rate=args.financing_rate,
        max_short_exposure=args.max_short_exposure,
        max_leverage=args.max_leverage,
    )

    response = requests.post(
        args.engine_url,
        headers=_headers(args.user_id, args.tenant_id),
        json=payload,
        timeout=args.timeout,
    )
    response.raise_for_status()
    result = response.json()
    _save_outputs(
        output_dir=output_dir,
        payload=payload,
        result=result,
        filtered_pred_path=filtered_pred_path,
        universe_path=universe_path,
    )

    summary = {
        "status": result.get("status"),
        "total_return": result.get("total_return"),
        "annual_return": result.get("annual_return"),
        "benchmark_return": result.get("benchmark_return"),
        "alpha": result.get("alpha"),
        "sharpe_ratio": result.get("sharpe_ratio"),
        "max_drawdown": result.get("max_drawdown"),
        "backtest_id": result.get("backtest_id"),
        "output_dir": str(output_dir.resolve()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
