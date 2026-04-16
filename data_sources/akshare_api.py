#!/usr/bin/env python3
"""
AkShare数据接口模块
提供股票基础信息、实时行情、历史数据等功能
"""

import logging
import sys
import time
from datetime import datetime

import akshare as ak
import pandas as pd

# 添加路径以便导入共享模块
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app/backend/shared")

# 导入字段常量
try:
    from backend.shared.schema.fields import CHINESE_TO_STD
except ImportError:
    try:
        from shared.schema.fields import CHINESE_TO_STD
    except ImportError:
        # 如果无法导入，使用空映射
        CHINESE_TO_STD = {}
        logging.warning("无法导入字段常量映射，使用空映射")


class AkShareAPI:
    """AkShare数据接口类"""

    def __init__(self, config: dict | None = None):
        """
        初始化AkShare API

        Args:
            config: 配置参数字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        # 获取配置对象
        config_obj = self.config.get_config()
        self.rate_limit_delay = getattr(
            config_obj.akshare.rate_limit, "delay", 0.1
        )  # 请求间隔

    def _rate_limit(self):
        """请求频率限制"""
        time.sleep(self.rate_limit_delay)

    def get_stock_list(self) -> pd.DataFrame | None:
        """
        获取A股股票列表

        Returns:
            pd.DataFrame: 股票列表数据，包含代码、名称、价格等信息
        """
        try:
            self.logger.info("开始获取股票列表")
            data = ak.stock_zh_a_spot_em()
            if data is not None and not data.empty:
                # 使用统一字段常量标准化列名
                rename_mapping = {}
                for chinese_col, std_col in CHINESE_TO_STD.items():
                    if chinese_col in data.columns:
                        rename_mapping[chinese_col] = std_col

                if rename_mapping:
                    data = data.rename(columns=rename_mapping)
                    self.logger.info(f"已标准化列名: {rename_mapping}")

                self.logger.info(f"成功获取股票列表，共{len(data)}只股票")
            return data
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return None

    def get_stock_info(self, symbol: str) -> dict | None:
        """
        获取股票基础信息

        Args:
            symbol: 股票代码

        Returns:
            股票基础信息字典
        """
        try:
            self._rate_limit()

            # 获取股票基本信息
            info = ak.stock_individual_info_em(symbol=symbol)

            if info is not None and not info.empty:
                # 转换为字典格式
                result = {
                    "symbol": symbol,
                    "name": info.get("股票简称", ""),
                    "industry": info.get("所属行业", ""),
                    "market_cap": info.get("总市值", 0),
                    "pe_ratio": info.get("市盈率", 0),
                    "pb_ratio": info.get("市净率", 0),
                    "update_time": datetime.now().isoformat(),
                }

                self.logger.info(f"获取股票{symbol}基础信息成功")
                return result
            else:
                self.logger.warning(f"股票{symbol}基础信息为空")
                return None

        except Exception as e:
            self.logger.error(f"获取股票{symbol}基础信息失败: {e}")
            return None

    def get_realtime_data(self, symbols: list[str]) -> dict | None:
        """
        获取股票实时行情数据

        Args:
            symbols: 股票代码列表

        Returns:
            Dict: 实时行情数据字典格式
        """
        try:
            self.logger.info(f"开始获取实时数据: {symbols}")

            # 获取全部股票数据
            data = ak.stock_zh_a_spot_em()
            if data is not None and not data.empty:
                # 使用统一字段常量标准化列名
                column_mapping = CHINESE_TO_STD.copy()
                # 补充标准映射中可能缺失的字段
                column_mapping.update(
                    {
                        "涨跌额": "change",
                        "成交量": "volume",
                        "成交额": "amount",
                        "最高": "high",
                        "最低": "low",
                        "今开": "open",
                        "昨收": "pre_close",
                    }
                )

                for old_col, new_col in column_mapping.items():
                    if old_col in data.columns:
                        data = data.rename(columns={old_col: new_col})

                # 过滤指定股票
                if "symbol" in data.columns:
                    symbol_data = data[data["symbol"].isin(symbols)]
                    if not symbol_data.empty:
                        # 转换为字典格式以匹配现有接口
                        result = {
                            "symbol": symbols,
                            "name": symbol_data.iloc[0].get("name", ""),
                            "price": float(symbol_data.iloc[0].get("price", 0)),
                            "change": float(symbol_data.iloc[0].get("change", 0)),
                            "change_pct": float(
                                symbol_data.iloc[0].get("change_pct", 0)
                            ),
                            "volume": int(symbol_data.iloc[0].get("volume", 0)),
                            "amount": float(symbol_data.iloc[0].get("amount", 0)),
                            "high": float(symbol_data.iloc[0].get("high", 0)),
                            "low": float(symbol_data.iloc[0].get("low", 0)),
                            "open": float(symbol_data.iloc[0].get("open", 0)),
                            "pre_close": float(symbol_data.iloc[0].get("pre_close", 0)),
                            "timestamp": datetime.now().isoformat(),
                        }
                        return result

            return None
        except Exception as e:
            self.logger.error(f"获取实时数据失败: {e}")
            return None

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = "qfq",
    ) -> pd.DataFrame | None:
        """
        获取股票历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 数据周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 ('qfq'-前复权, 'hfq'-后复权, ''-不复权)

        Returns:
            pd.DataFrame: 历史数据
        """
        try:
            self.logger.info(
                f"开始获取股票{symbol}历史数据: {start_date} 到 {end_date}"
            )

            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust,
            )

            if df is not None and not df.empty:
                # 标准化列名
                column_mapping = {
                    "日期": "date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "volume",
                    "成交额": "amount",
                    "振幅": "amplitude",
                    "涨跌幅": "change_pct",
                    "涨跌额": "change",
                    "换手率": "turnover",
                }

                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns:
                        df = df.rename(columns={old_col: new_col})

                # 确保日期列为datetime类型
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")

                self.logger.info(f"获取股票{symbol}历史数据成功，共{len(df)}条记录")
                return df
            else:
                self.logger.warning(f"股票{symbol}历史数据为空")
                return pd.DataFrame()  # 返回空DataFrame而不是None

        except Exception as e:
            self.logger.error(f"获取股票{symbol}历史数据失败: {e}")
            return pd.DataFrame()  # 返回空DataFrame而不是None

    def get_market_overview(self) -> dict | None:
        """
        获取市场概览数据

        Returns:
            市场概览数据字典
        """
        try:
            self._rate_limit()

            # 获取A股市场总貌
            market_data = ak.stock_zh_a_spot_em()

            if market_data is not None and not market_data.empty:
                # 计算市场统计数据
                total_stocks = len(market_data)
                rising_stocks = len(market_data[market_data["涨跌幅"] > 0])
                falling_stocks = len(market_data[market_data["涨跌幅"] < 0])
                unchanged_stocks = len(market_data[market_data["涨跌幅"] == 0])

                result = {
                    "total_stocks": total_stocks,
                    "rising_stocks": rising_stocks,
                    "falling_stocks": falling_stocks,
                    "unchanged_stocks": unchanged_stocks,
                    "rising_ratio": round(rising_stocks / total_stocks * 100, 2),
                    "falling_ratio": round(falling_stocks / total_stocks * 100, 2),
                    "avg_change_pct": round(market_data["涨跌幅"].mean(), 2),
                    "total_volume": int(market_data["成交量"].sum()),
                    "total_amount": float(market_data["成交额"].sum()),
                    "update_time": datetime.now().isoformat(),
                }

                self.logger.info("获取市场概览数据成功")
                return result
            else:
                self.logger.warning("市场概览数据为空")
                return None

        except Exception as e:
            self.logger.error(f"获取市场概览数据失败: {e}")
            return None

    def search_stock(self, keyword: str) -> list[dict] | None:
        """
        搜索股票

        Args:
            keyword: 搜索关键词（股票代码或名称）

        Returns:
            搜索结果列表
        """
        try:
            self._rate_limit()

            # 获取所有股票列表
            all_stocks = ak.stock_info_a_code_name()

            if all_stocks is not None and not all_stocks.empty:
                # 搜索匹配的股票
                matches = all_stocks[
                    (all_stocks["code"].str.contains(
                        keyword, case=False, na=False))
                    | (all_stocks["name"].str.contains(keyword, case=False, na=False))
                ]

                if not matches.empty:
                    results = []
                    for _, row in matches.iterrows():
                        results.append(
                            {"symbol": row["code"], "name": row["name"]})

                    self.logger.info(f"搜索关键词'{keyword}'找到{len(results)}个结果")
                    return results
                else:
                    self.logger.info(f"搜索关键词'{keyword}'未找到匹配结果")
                    return []
            else:
                self.logger.warning("股票列表数据为空")
                return None

        except Exception as e:
            self.logger.error(f"搜索股票失败: {e}")
            return None

    def get_index_data(self, index_code: str = "000001") -> dict | None:
        """
        获取指数数据

        Args:
            index_code: 指数代码 (默认上证指数)

        Returns:
            指数数据字典
        """
        try:
            self._rate_limit()

            # 获取指数实时数据
            df = ak.stock_zh_index_spot_em()

            if df is not None and not df.empty:
                # 查找指定指数
                index_data = df[df["代码"] == index_code]

                if not index_data.empty:
                    row = index_data.iloc[0]
                    result = {
                        "code": index_code,
                        "name": row.get("名称", ""),
                        "price": float(row.get("最新价", 0)),
                        "change": float(row.get("涨跌额", 0)),
                        "change_pct": float(row.get("涨跌幅", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "open": float(row.get("今开", 0)),
                        "pre_close": float(row.get("昨收", 0)),
                        "timestamp": datetime.now().isoformat(),
                    }

                    self.logger.info(f"获取指数{index_code}数据成功")
                    return result
                else:
                    self.logger.warning(f"未找到指数{index_code}的数据")
                    return None
            else:
                self.logger.warning("指数数据为空")
                return None

        except Exception as e:
            self.logger.error(f"获取指数{index_code}数据失败: {e}")
            return None
