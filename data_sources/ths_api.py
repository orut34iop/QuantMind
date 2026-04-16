import logging
import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


class THSAPI:
    def __init__(self):
        self.logger = logger

    def get_financial_data(self, symbol: str) -> pd.DataFrame | None:
        """
        获取财务数据 (ROE等)
        """
        try:
            df = ak.stock_financial_abstract_ths(symbol=symbol)
            if df is not None and not df.empty:
                # 净资产收益率(%) -> ROE
                # 报告期 -> trade_date (需要对齐)
                return df
            return None
        except Exception as e:
            self.logger.error(
                f"Error fetching financial summary for {symbol}: {e}")
            return None

    def get_valuation_data(self, symbol: str) -> pd.DataFrame | None:
        """
        获取历史估值指标 (PE, PB, PS)
        EastMoney (东方财富) 接口获取每日历史指标
        """
        try:
            df = ak.stock_zh_a_indicator_em(symbol=symbol)
            if df is not None and not df.empty:
                # 东方财富接口列名:
                # 日期, 市盈率-动态, 市净率, 市销率...
                # 我们需要映射到 trade_date, pe, pb, ps
                column_mapping = {
                    "日期": "trade_date",
                    "市盈率-动态": "pe",
                    "市净率": "pb",
                    "市销率": "ps",
                }
                df = df.rename(columns=column_mapping)
                return df
            return None
        except Exception as e:
            self.logger.error(
                f"Error fetching valuation data for {symbol}: {e}")
            return None


_ths_api = None


def get_ths_api():
    global _ths_api
    if _ths_api is None:
        _ths_api = THSAPI()
    return _ths_api
