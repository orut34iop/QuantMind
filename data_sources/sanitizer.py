#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗与质量控制模块
负责检测并修复原始数据中的 NaN、零值和异常值
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DataSanitizer:
    """
    数据清洗器
    专门针对金融行情数据进行质量修复
    """

    @staticmethod
    def sanitize_historical_data(
        df: pd.DataFrame, symbol: str = "Unknown", fill_limit: int = 5
    ) -> pd.DataFrame:
        """
        清洗历史行情数据

        Args:
            df: 原始 DataFrame
            symbol: 股票代码（用于日志）
            fill_limit: 最大连续填充天数，超过此数则认为该标的数据不可靠

        Returns:
            清洗后的 DataFrame
        """
        if df is None or df.empty:
            return df

        # 复制一份，避免副作用
        df = df.copy()

        # 1. 确保核心列存在 (兼容不同 API 返回的列名)
        core_columns = {
            "open": ["$open", "open", "开盘"],
            "high": ["$high", "high", "最高"],
            "low": ["$low", "low", "最低"],
            "close": ["$close", "close", "收盘"],
            "volume": ["$volume", "volume", "成交量"],
        }

        # 映射列名到标准格式
        column_mapping = {}
        for std_name, aliases in core_columns.items():
            for alias in aliases:
                if alias in df.columns:
                    column_mapping[alias] = std_name
                    break

        if len(column_mapping) < 4:  # 至少需要 OHLC
            logger.warning(f"[{symbol}] 数据列不足，跳过清洗: {df.columns.tolist()}")
            return df

        # 2. 检测 NaN
        nan_count = df.isna().sum().sum()
        if nan_count > 0:
            logger.info(f"[{symbol}] 检测到 {nan_count} 个 NaN 值，启动修复程序...")

            # 记录缺失位置以便追踪
            missing_dates = df[df.isna().any(axis=1)].index.tolist()
            logger.debug(f"[{symbol}] 缺失日期示例: {missing_dates[:5]}")

            # 执行前向填充 (ffill) - 使用前一天的价格
            # 注意：成交量 volume 应该填充为 0 而不是 ffill
<<<<<<< HEAD
            vol_col = next((c for c in df.columns if c in core_columns["volume"]), None)
=======
            vol_col = next(
                (c for c in df.columns if c in core_columns["volume"]), None)
>>>>>>> refactor/service-cleanup
            price_cols = [c for c in df.columns if c != vol_col]

            # 价格前向填充
            df[price_cols] = df[price_cols].ffill(limit=fill_limit)
            # 如果开头就是缺失，则尝试后向填充一次
            df[price_cols] = df[price_cols].bfill(limit=1)

            # 成交量填充为 0
            if vol_col:
                df[vol_col] = df[vol_col].fillna(0)

        # 3. 处理零值 (金融数据中价格不应为 0)
        for col in [
            c
            for c in df.columns
            if c in column_mapping and column_mapping[c] != "volume"
        ]:
            zero_mask = df[col] <= 0
            if zero_mask.any():
                zero_count = zero_mask.sum()
                logger.warning(
                    f"[{symbol}] 检测到 {zero_count} 个非正价格，尝试修复..."
                )
                df.loc[zero_mask, col] = np.nan
                df[col] = df[col].ffill().bfill()

        # 4. 最终质量检查
        remaining_nans = df.isna().sum().sum()
        if remaining_nans > 0:
            logger.error(
                f"[{symbol}] 清洗后仍残余 {remaining_nans} 个 NaN，建议检查数据源。"
            )
        else:
            if nan_count > 0:
                logger.info(f"[{symbol}] 数据清洗完成，质量已达标。")

        return df

    @staticmethod
    def check_data_integrity(df: pd.DataFrame) -> Dict[str, Any]:
        """
        数据完整性检查报告
        """
        return {
            "is_empty": df is None or df.empty,
            "row_count": len(df) if df is not None else 0,
            "nan_count": int(df.isna().sum().sum()) if df is not None else 0,
            "has_zero_prices": (
                (df.select_dtypes(include=[np.number]) <= 0).any().any()
                if df is not None
                else False
            ),
        }
