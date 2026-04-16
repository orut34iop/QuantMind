"""Step 1: 股票池选择 - 条件解析与 DSL 生成"""

import logging
import os
import re
from typing import Any, Dict, List

from ..api.schemas.stock_pool import (
    Condition,
    ParseResponse,
)

logger = logging.getLogger(__name__)

FACTOR_COLUMN_MAP = {
    "market_cap": "total_mv",
    "pe": "pe_ttm",
    "pe_ttm": "pe_ttm",
    "pb": "pb",
    "ps": "ps_ratio",
    "volume": "volume",
    "amount": "turnover",
    "close": "close",
    "turnover_rate": "turnover_rate",
    "pct_chg": "pct_change",
    "roe": "roe",
    "net_profit_growth": "net_profit_growth",
    "industry": "industry",
    "is_st": "is_st",
    # 兼容两种命名：运行时由 Step2 按数据表实际列名做最终映射
    "is_hs300": "is_hs300",
    "hs300": "is_hs300",
    "is_csi300": "is_hs300",
    "csi300": "is_hs300",
    "is_csi1000": "is_csi1000",
    "csi1000": "is_csi1000",
    "is_suspended": "is_suspended",
    "is_listed_over_1y": "is_listed_over_1y",
    "rsi": "rsi",
    "rsi_6": "rsi",
    "rsi_12": "rsi",
    "rsi_14": "rsi",
    "macd": "macd_hist",
    "dif": "macd_dif",
    "dea": "macd_dea",
    "macd_dif": "macd_dif",
    "macd_dea": "macd_dea",
    "macd_hist": "macd_hist",
    "kdj_k": "kdj_k",
    "kdj_d": "kdj_d",
    "kdj_j": "kdj_j",
    "sma5": "sma5",
    "sma20": "sma20",
    "sma60": "sma60",
}

DSL_PREFIX = "SELECT symbol WHERE "
DELTA_REGEX = re.compile(
    r"DELTA\((?P<factor>[a-zA-Z0-9_]+),(?P<window>\d+)\)\s*" r"(?P<op>>=|<=|==|!=|>|<)\s*(?P<value>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
SIMPLE_REGEX = re.compile(
    r"(?P<factor>[a-zA-Z0-9_]+)\s*" r"(?P<op>>=|<=|==|!=|>|<)\s*(?P<value>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
COMBINER_REGEX = re.compile(r"\s+(AND|OR)\s+", re.IGNORECASE)
MAX_LOOKBACK_DAYS = 400
LATEST_TABLE = "stock_daily_latest"

# total_mv 列口径可配置：默认“万元”（1亿=10000）。
# 若你的数据库是“千元”，可通过环境变量 AI_STRATEGY_TOTAL_MV_PER_YI=100000 覆盖。
MARKET_CAP_YI_TO_DB_UNIT = float(os.getenv("AI_STRATEGY_TOTAL_MV_PER_YI", "10000"))


def _condition_to_dsl(cond: Condition) -> str:
    t = cond.get("type")
    if t == "numeric":
        factor = cond["factor"]
        threshold = cond["threshold"]
        if factor == "market_cap":
            threshold = float(threshold) * MARKET_CAP_YI_TO_DB_UNIT
        return f"SELECT symbol WHERE {factor} {cond['operator']} {threshold}"
    if t == "trend":
        sign = "> 0" if cond.get("direction") == "up" else "< 0"
        return f"SELECT symbol WHERE DELTA({cond['factor']},{cond['window']}) {sign}"
    if t == "composite":
        children = cond.get("children", [])
        parts = [_condition_to_dsl(c).replace("SELECT symbol WHERE ", "") for c in children]
        op = cond.get("op", "AND").upper()
        return "SELECT symbol WHERE " + (f" {op} ".join(parts) if parts else "true")
    raise ValueError(f"未知条件类型: {t}")


def _extract_factors(cond: Condition) -> list[str]:
    t = cond.get("type")
    if t in ("numeric", "trend"):
        return [cond.get("factor")]
    if t == "composite":
        facs: list[str] = []
        for c in cond.get("children", []):
            facs.extend(_extract_factors(c))
        return facs
    return []


def _parse_dsl(dsl: str) -> tuple[list[dict[str, Any]], list[str]]:
    expr = dsl[len(DSL_PREFIX) :].strip()
    if not expr or expr.lower() == "true":
        return [], []

    parts = COMBINER_REGEX.split(expr)
    conditions: list[dict[str, Any]] = []
    combiners: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            combiners.append(part.upper())
            continue

        text_part = part.strip()
        match = DELTA_REGEX.match(text_part)
        if match:
            conditions.append(
                {
                    "type": "delta",
                    "factor": match.group("factor"),
                    "window": int(match.group("window")),
                    "op": match.group("op"),
                    "value": float(match.group("value")),
                }
            )
            continue

        match = SIMPLE_REGEX.match(text_part)
        if match:
            conditions.append(
                {
                    "type": "simple",
                    "factor": match.group("factor"),
                    "op": match.group("op"),
                    "value": float(match.group("value")),
                }
            )
            continue

        raise ValueError(f"无法解析条件: {text_part}")

    if combiners and len(combiners) != len(conditions) - 1:
        raise ValueError("DSL条件解析失败：连接符数量异常")

    return conditions, combiners


def _map_factor(factor: str) -> str:
    key = factor.strip()
    if key not in FACTOR_COLUMN_MAP:
        raise ValueError(f"暂不支持的因子: {factor}")
    return FACTOR_COLUMN_MAP[key]


def parse_conditions(conditions: Condition) -> ParseResponse:
    """解析前端条件树为 DSL 语句"""
    dsl = _condition_to_dsl(conditions)
    mapping = {"factors": _extract_factors(conditions)}
    warnings = []
    suggestions = []
    if "market_cap" in mapping["factors"]:
        suggestions.append("可考虑加入行业过滤以提升针对性")
    return ParseResponse(
        dsl=dsl,
        mapping=mapping,
        warnings=warnings,
        confidence=0.95,
        suggestions=suggestions,
        version="1.0.0",
    )
