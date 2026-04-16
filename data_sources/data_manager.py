#!/usr/bin/env python3
"""
数据管理集成模块
将akshare接口集成到现有的数据管理系统中
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# 导入akshare接口
from .akshare_api import AkShareAPI
from .cache import SimpleCache

# 导入现有的数据管理组件
try:
    from backend.data_management.main import DataFile, DataManagementService, DataSource
    from backend.market_data.database.dao import DAOFactory
    from backend.market_data.database.integration import DatabaseIntegration
except ImportError:
    # 如果无法导入，创建简化的接口
    class DataManagementService:
        pass

    class DataSource:
        pass

    class DataFile:
        pass

    class DAOFactory:
        pass

    class DatabaseIntegration:
        pass


class IntegratedDataManager:
    """
    集成数据管理器
    整合akshare接口和现有数据管理系统
    """

    def __init__(self, config: dict | None = None):
        """
        初始化集成数据管理器

        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.logger = self._setup_logger()

        # 初始化各个组件
        try:
            # 初始化AkShare API
            self.akshare_api = AkShareAPI(self.config)

            # 初始化缓存
            if self.config:
                config_obj = self.config.get_config()
                cache_config = config_obj.cache
            else:
                cache_config = {}
            if isinstance(cache_config, dict):
                max_size = cache_config.get("max_size", 1000)
                default_ttl = cache_config.get("default_ttl", 300)
            else:
                max_size = getattr(cache_config, "max_size", 1000)
                default_ttl = getattr(cache_config, "default_ttl", 300)

            self.cache = SimpleCache(
                max_size=max_size, default_ttl=default_ttl)

            # 设置缓存启用状态
            self.cache_enabled = True
            self._cache = {}

            # 初始化数据管理服务（如果可用）
            try:
                from backend.data_management.main import data_management_service

                self.data_service = data_management_service
            except ImportError:
                self.logger.warning("数据管理服务不可用，将使用本地缓存")
                self.data_service = None

            self.logger.info("集成数据管理器初始化成功")

        except Exception as e:
            self.logger.error(f"集成数据管理器初始化失败: {e}")
            raise

    def _setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _get_cache_key(self, source: str, params: dict) -> str:
        """生成缓存键"""
        import hashlib

        key_str = f"{source}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """检查缓存是否有效"""
        if not cache_entry:
            return False

        cache_time = cache_entry.get("timestamp")
        if not cache_time:
            return False

        return (datetime.now() - cache_time).seconds < self.cache_duration

    def _set_cache(self, key: str, data: Any) -> None:
        """设置缓存"""
        if self.cache_enabled:
            self._cache[key] = {"data": data, "timestamp": datetime.now()}

    def _get_cache(self, key: str) -> Any | None:
        """获取缓存"""
        if not self.cache_enabled:
            return None

        cache_entry = self._cache.get(key)
        if self._is_cache_valid(cache_entry):
            return cache_entry["data"]

            # 清理过期缓存
        if key in self._cache:
            del self._cache[key]

        return None

    async def get_stock_list(
        self, market: str = "A", use_cache: bool = True
    ) -> pd.DataFrame | None:
        """
        获取股票列表

        Args:
            market: 市场类型
            use_cache: 是否使用缓存

        Returns:
            股票列表DataFrame
        """
        try:
            cache_key = self._get_cache_key("stock_list", {"market": market})

            # 检查缓存
            if use_cache:
                cached_data = self._get_cache(cache_key)
                if cached_data is not None:
                    self.logger.info(f"从缓存获取{market}市场股票列表")
                    return cached_data

                    # 从akshare获取数据
            data = self.akshare_api.get_stock_list(market)

            if data is not None:
                # 设置缓存
                self._set_cache(cache_key, data)

                # 记录到数据管理系统
                await self._log_data_access(
                    "stock_list",
                    {"market": market, "records_count": len(
                        data), "source": "akshare"},
                )

                self.logger.info(f"获取{market}市场股票列表成功，共{len(data)}只股票")

            return data

        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            return None

    async def get_realtime_data(
        self, symbols: str | list[str], use_cache: bool = True
    ) -> dict[str, Any]:
        """
        获取实时行情数据

        Args:
            symbols: 股票代码或代码列表
            use_cache: 是否使用缓存

        Returns:
            实时行情数据字典
        """
        try:
            if isinstance(symbols, str):
                symbols = [symbols]

            results = {}

            for symbol in symbols:
                cache_key = self._get_cache_key("realtime", {"symbol": symbol})

                # 检查缓存
                if use_cache:
                    cached_data = self._get_cache(cache_key)
                    if cached_data is not None:
                        results[symbol] = cached_data
                        continue

                        # 从akshare获取数据
                data = self.akshare_api.get_realtime_data(symbol)

                if data is not None:
                    results[symbol] = data
                    # 设置缓存
                    self._set_cache(cache_key, data)
                else:
                    results[symbol] = None

                    # 记录到数据管理系统
            await self._log_data_access(
                "realtime",
                {
                    "symbols": symbols,
                    "success_count": len(
                        [r for r in results.values() if r is not None]
                    ),
                    "source": "akshare",
                },
            )

            return results

        except Exception as e:
            self.logger.error(f"获取实时行情失败: {e}")
            return {}

    async def get_batch_realtime_data(
        self, symbols: list[str], use_cache: bool = True
    ) -> dict[str, dict]:
        """
        批量获取股票实时数据

        Args:
            symbols: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            Dict[str, Dict]: 股票代码到实时数据的映射
        """
        try:
            result = {}

            # 逐个获取实时数据
            for symbol in symbols:
                cache_key = self._get_cache_key("realtime", {"symbol": symbol})

                # 检查缓存
                if use_cache:
                    cached_data = self._get_cache(cache_key)
                    if cached_data is not None:
                        result[symbol] = cached_data
                        continue

                        # 从akshare获取数据
                data = self.akshare_api.get_realtime_data(symbol)

                if data is not None:
                    result[symbol] = data
                    # 设置缓存
                    if use_cache:
                        self._set_cache(cache_key, data)
                else:
                    result[symbol] = None

                    # 避免请求过于频繁
                import time

                time.sleep(0.1)

                # 记录到数据管理系统
            await self._log_data_access(
                "batch_realtime",
                {
                    "symbols": symbols,
                    "success_count": len([r for r in result.values() if r is not None]),
                    "source": "akshare",
                },
            )

            self.logger.info(
                f"批量获取实时数据完成，成功获取{len([r for r in result.values() if r is not None])}只股票"
            )
            return result

        except Exception as e:
            self.logger.error(f"批量获取实时数据失败: {e}")
            return {}

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame | None:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            period: 时间周期
            start_date: 开始日期
            end_date: 结束日期
            use_cache: 是否使用缓存

        Returns:
            历史数据DataFrame
        """
        try:
            cache_key = self._get_cache_key(
                "historical",
                {
                    "symbol": symbol,
                    "period": period,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

            # 检查缓存
            if use_cache:
                cached_data = self._get_cache(cache_key)
                if cached_data is not None:
                    self.logger.info(f"从缓存获取{symbol}历史数据")
                    return cached_data

                    # 从akshare获取数据
                    data = self.akshare_api.get_historical_data(
                        symbol, period, start_date, end_date
                    )

                    if data is not None:
                        # 数据清洗与预处理
                        from .sanitizer import DataSanitizer

                        data = DataSanitizer.sanitize_historical_data(
                            data, symbol=symbol
                        )

                        # 设置缓存
                        self._set_cache(cache_key, data)

                # 记录到数据管理系统
                await self._log_data_access(
                    "historical",
                    {
                        "symbol": symbol,
                        "period": period,
                        "records_count": len(data),
                        "source": "akshare",
                    },
                )

                self.logger.info(f"获取{symbol}历史数据成功，共{len(data)}条记录")

            return data

        except Exception as e:
            self.logger.error(f"获取历史数据失败: {e}")
            return None

    async def get_market_overview(self, use_cache: bool = True) -> dict | None:
        """
        获取市场概览

        Args:
            use_cache: 是否使用缓存

        Returns:
            市场概览数据
        """
        try:
            cache_key = self._get_cache_key("market_overview", {})

            # 检查缓存
            if use_cache:
                cached_data = self._get_cache(cache_key)
                if cached_data is not None:
                    self.logger.info("从缓存获取市场概览数据")
                    return cached_data

                    # 从akshare获取数据
            data = self.akshare_api.get_market_overview()

            if data is not None:
                # 设置缓存
                self._set_cache(cache_key, data)

                # 记录到数据管理系统
                await self._log_data_access(
                    "market_overview",
                    {"total_stocks": data.get(
                        "total_stocks", 0), "source": "akshare"},
                )

                self.logger.info("获取市场概览数据成功")

            return data

        except Exception as e:
            self.logger.error(f"获取市场概览失败: {e}")
            return None

    async def search_stock(self, keyword: str) -> list[dict] | None:
        """
        搜索股票

        Args:
            keyword: 搜索关键词

        Returns:
            搜索结果列表
        """
        try:
            results = self.akshare_api.search_stock(keyword)

            if results is not None:
                # 记录到数据管理系统
                await self._log_data_access(
                    "search",
                    {
                        "keyword": keyword,
                        "results_count": len(results),
                        "source": "akshare",
                    },
                )

                self.logger.info(f"搜索'{keyword}'找到{len(results)}个结果")

            return results

        except Exception as e:
            self.logger.error(f"搜索股票失败: {e}")
            return None

    async def export_data_to_csv(
        self, data: pd.DataFrame, filename: str, output_dir: str = "./exports"
    ) -> str:
        """
        导出数据到CSV文件

        Args:
            data: 要导出的数据
            filename: 文件名
            output_dir: 输出目录

        Returns:
            导出文件路径
        """
        try:
            # 创建输出目录
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            # 生成文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = Path(output_dir) / f"{filename}_{timestamp}.csv"

            # 导出数据
            data.to_csv(file_path, index=False, encoding="utf-8-sig")

            self.logger.info(f"数据导出成功: {file_path}")
            return str(file_path)

        except Exception as e:
            self.logger.error(f"数据导出失败: {e}")
            raise

    async def _log_data_access(self, operation: str, details: dict) -> None:
        """
        记录数据访问日志

        Args:
            operation: 操作类型
            details: 操作详情
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "details": details,
                "source": "integrated_data_manager",
            }

            # 这里可以扩展为写入数据库或文件
            self.logger.info(
                f"数据访问记录: {json.dumps(log_entry, ensure_ascii=False)}"
            )

        except Exception as e:
            self.logger.warning(f"记录数据访问日志失败: {e}")

    async def get_data_statistics(self) -> dict[str, Any]:
        """
        获取数据统计信息

        Returns:
            数据统计信息
        """
        try:
            stats = {
                "cache_size": len(self._cache),
                "cache_enabled": self.cache_enabled,
                "available_sources": list(self.data_sources.keys()),
                "akshare_status": "available",
                "last_update": datetime.now().isoformat(),
            }

            # 添加缓存统计
            if self._cache:
                cache_stats = {
                    "total_entries": len(self._cache),
                    "valid_entries": len(
                        [k for k, v in self._cache.items() if self._is_cache_valid(v)]
                    ),
                    "expired_entries": len(
                        [
                            k
                            for k, v in self._cache.items()
                            if not self._is_cache_valid(v)
                        ]
                    ),
                }
                stats["cache_stats"] = cache_stats

            return stats

        except Exception as e:
            self.logger.error(f"获取数据统计失败: {e}")
            return {}

    async def clear_cache(self) -> bool:
        """
        清理缓存

        Returns:
            是否成功
        """
        try:
            cache_size = len(self._cache)
            self._cache.clear()

            self.logger.info(f"缓存清理成功，清理了{cache_size}个条目")
            return True

        except Exception as e:
            self.logger.error(f"缓存清理失败: {e}")
            return False

    def get_available_data_sources(self) -> dict[str, str]:
        """
        获取可用的数据源

        Returns:
            数据源字典
        """
        return self.data_sources.copy()

        # 全局数据管理器实例


_global_data_manager = None


def get_data_manager(config: dict | None = None) -> IntegratedDataManager:
    """
    获取全局数据管理器实例

    Args:
        config: 配置参数

    Returns:
        数据管理器实例
    """
    global _global_data_manager

    if _global_data_manager is None:
        _global_data_manager = IntegratedDataManager(config)

    return _global_data_manager
