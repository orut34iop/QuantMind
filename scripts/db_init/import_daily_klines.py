#!/usr/bin/env python3
"""
日线数据导入脚本
文件: import_daily_klines.py
功能: 从akshare导入全市场A股日线数据到PostgreSQL
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import psycopg2
from psycopg2.extras import execute_batch

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(
        "import_daily_klines.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# 数据库配置
DB_CONFIG = {
    "host": "192.168.1.88",
    "port": 6789,
    "user": "quantmind",
    "password": "admin123",
    "database": "quantmind",
}

# 导入配置
IMPORT_CONFIG = {
    "start_date": "2020-01-01",  # 开始日期
    "batch_size": 500,  # 批量插入大小
    "request_delay": 0.5,  # 请求延迟（秒）
    "retry_times": 3,  # 重试次数
    "save_interval": 100,  # 每N个股票保存一次进度
}


class DailyKlinesImporter:
    """日线数据导入器"""

    def __init__(self):
        self.conn = None
        self.cur = None
        self.total_stocks = 0
        self.success_count = 0
        self.fail_count = 0
        self.total_records = 0

    def connect_db(self):
        """连接数据库"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cur = self.conn.cursor()
            logger.info("✅ 数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False

    def close_db(self):
        """关闭数据库连接"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("数据库连接已关闭")

    def get_stock_list(self) -> List[Dict]:
        """获取A股股票列表"""
        try:
            logger.info("📊 获取A股股票列表...")
            df = ak.stock_zh_a_spot_em()

            stocks = []
            for _, row in df.iterrows():
                code = row["代码"]
                # 判断市场
                if code.startswith("6"):
                    market = "SH"
                elif code.startswith(("0", "3")):
                    market = "SZ"
                else:
                    continue

                stocks.append(
                    {"code": code, "symbol": f"{code}.{market}",
                        "name": row["名称"]}
                )

            self.total_stocks = len(stocks)
            logger.info(f"✅ 获取到 {self.total_stocks} 只股票")
            return stocks

        except Exception as e:
            logger.error(f"❌ 获取股票列表失败: {e}")
            return []

    def fetch_stock_daily_data(
        self, code: str, symbol: str, start_date: str = None
    ) -> Optional[List[Dict]]:
        """
        获取单只股票的日线数据

        Args:
            code: 股票代码（不带后缀）
            symbol: 完整代码（带.SH或.SZ）
            start_date: 开始日期

        Returns:
            数据记录列表，失败返回None
        """
        if start_date is None:
            start_date = IMPORT_CONFIG["start_date"]

        retry_count = 0
        while retry_count < IMPORT_CONFIG["retry_times"]:
            try:
                # 获取数据
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    adjust="qfq",  # 前复权
                )

                if df.empty:
                    logger.warning(f"⚠️  {symbol} 无数据")
                    return []

                # 转换数据格式
                records = []
                for _, row in df.iterrows():
                    record = {
                        "symbol": symbol,
                        "trade_date": row["日期"],
                        "open_price": float(row["开盘"]),
                        "high_price": float(row["最高"]),
                        "low_price": float(row["最低"]),
                        "close_price": float(row["收盘"]),
                        "volume": int(row["成交量"]),
                        "amount": float(row["成交额"]),
                        "change": float(row["涨跌额"]) if "涨跌额" in row else None,
                        "change_pct": float(row["涨跌幅"]) if "涨跌幅" in row else None,
                        "amplitude": float(row["振幅"]) if "振幅" in row else None,
                        "turnover_rate": (
                            float(row["换手率"]) if "换手率" in row else None
                        ),
                    }
                    records.append(record)

                logger.debug(f"✅ {symbol} 获取 {len(records)} 条数据")
                return records

            except Exception as e:
                retry_count += 1
                logger.warning(f"⚠️  {symbol} 第{retry_count}次尝试失败: {e}")
                time.sleep(1)

        logger.error(
            f"❌ {symbol} 获取数据失败，已重试{IMPORT_CONFIG['retry_times']}次"
        )
        return None

    def insert_daily_data(self, records: List[Dict]) -> bool:
        """
        批量插入日线数据

        Args:
            records: 数据记录列表

        Returns:
            是否成功
        """
        if not records:
            return True

        insert_sql = """
            INSERT INTO daily_klines
            (symbol, trade_date, open_price, high_price, low_price,
             close_price, volume, amount, change, change_pct,
             amplitude, turnover_rate, data_source)
            VALUES (
                %(symbol)s, %(trade_date)s, %(open_price)s,
                %(high_price)s, %(low_price)s, %(close_price)s,
                %(volume)s, %(amount)s, %(change)s, %(change_pct)s,
                %(amplitude)s, %(turnover_rate)s, 'akshare'
            )
            ON CONFLICT (symbol, trade_date) DO UPDATE SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount,
                change = EXCLUDED.change,
                change_pct = EXCLUDED.change_pct,
                amplitude = EXCLUDED.amplitude,
                turnover_rate = EXCLUDED.turnover_rate,
                updated_at = CURRENT_TIMESTAMP;
        """

        try:
            execute_batch(
                self.cur, insert_sql, records, page_size=IMPORT_CONFIG["batch_size"]
            )
            self.conn.commit()
            self.total_records += len(records)
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ 插入数据失败: {e}")
            return False

    def import_stock(self, stock: Dict) -> bool:
        """
        导入单只股票数据

        Args:
            stock: 股票信息字典

        Returns:
            是否成功
        """
        symbol = stock["symbol"]
        code = stock["code"]
        name = stock["name"]

        try:
            # 获取数据
            records = self.fetch_stock_daily_data(code, symbol)

            if records is None:
                return False

            if not records:
                logger.info(f"⚪ {symbol} {name}: 无数据")
                return True

            # 插入数据库
            if self.insert_daily_data(records):
                logger.info(f"✅ {symbol} {name}: {len(records)}条数据")
                return True
            else:
                logger.error(f"❌ {symbol} {name}: 插入失败")
                return False

        except Exception as e:
            logger.error(f"❌ {symbol} {name}: {e}")
            return False

    def import_all_stocks(self, limit: int = None):
        """
        导入全部股票数据

        Args:
            limit: 限制导入数量（测试用）
        """
        # 获取股票列表
        stocks = self.get_stock_list()
        if not stocks:
            logger.error("无法获取股票列表，退出")
            return

        if limit:
            stocks = stocks[:limit]
            logger.info(f"⚠️  测试模式：仅导入前{limit}只股票")

        # 连接数据库
        if not self.connect_db():
            return

        # 开始导入
        logger.info("=" * 80)
        logger.info(f"🚀 开始导入，共 {len(stocks)} 只股票")
        logger.info(f"开始日期: {IMPORT_CONFIG['start_date']}")
        logger.info("=" * 80)

        start_time = time.time()

        for i, stock in enumerate(stocks, 1):
            logger.info(
                f"\n[{i}/{len(stocks)}] 处理 {stock['symbol']} {stock['name']}")

            if self.import_stock(stock):
                self.success_count += 1
            else:
                self.fail_count += 1

            # 进度汇报
            if i % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / i
                remain_time = avg_time * (len(stocks) - i)

                logger.info(f"\n{'='*80}")
                logger.info(
                    f"📊 进度: {i}/{len(stocks)} ({i/len(stocks)*100:.1f}%)")
                logger.info(
                    f"✅ 成功: {self.success_count}, ❌ 失败: {self.fail_count}"
                )
                logger.info(f"📝 总记录: {self.total_records:,}条")
                logger.info(
                    f"⏱️  已用时: {elapsed/60:.1f}分钟, 预计剩余: {remain_time/60:.1f}分钟"
                )
                logger.info(f"{'='*80}\n")

            # 请求延迟
            time.sleep(IMPORT_CONFIG["request_delay"])

        # 完成汇总
        total_time = time.time() - start_time
        logger.info("\n" + "=" * 80)
        logger.info("🎉 导入完成！")
        logger.info("=" * 80)
        logger.info(f"总股票数: {len(stocks)}")
        logger.info(f"✅ 成功: {self.success_count}")
        logger.info(f"❌ 失败: {self.fail_count}")
        logger.info(f"📝 总记录: {self.total_records:,}条")
        logger.info(f"⏱️  总用时: {total_time/60:.1f}分钟")
        logger.info(f"⚡ 平均速度: {self.total_records/(total_time/60):.0f}条/分钟")
        logger.info("=" * 80)

        # 关闭连接
        self.close_db()

    def update_recent_data(self, days: int = 7):
        """
        更新最近N天的数据

        Args:
            days: 更新最近几天的数据
        """
        start_date = (datetime.now() - timedelta(days=days)
                      ).strftime("%Y-%m-%d")

        logger.info(f"🔄 更新模式：仅更新{start_date}之后的数据")

        # 临时修改配置
        old_start_date = IMPORT_CONFIG["start_date"]
        IMPORT_CONFIG["start_date"] = start_date

        # 执行导入
        self.import_all_stocks()

        # 恢复配置
        IMPORT_CONFIG["start_date"] = old_start_date


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="导入股票日线数据")
    parser.add_argument(
        "--mode", choices=["full", "update", "test"], default="full", help="导入模式"
    )
    parser.add_argument("--limit", type=int, help="限制导入数量（测试用）")
    parser.add_argument("--days", type=int, default=7, help="更新模式下的天数")
    parser.add_argument("--start-date", type=str, help="开始日期（YYYY-MM-DD）")

    args = parser.parse_args()

    # 更新配置
    if args.start_date:
        IMPORT_CONFIG["start_date"] = args.start_date

    # 创建导入器
    importer = DailyKlinesImporter()

    # 执行导入
    try:
        if args.mode == "test":
            logger.info("🧪 测试模式")
            importer.import_all_stocks(limit=args.limit or 10)
        elif args.mode == "update":
            logger.info("🔄 更新模式")
            importer.update_recent_data(days=args.days)
        else:
            logger.info("📥 完整导入模式")
            importer.import_all_stocks(limit=args.limit)
    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断导入")
        importer.close_db()
    except Exception as e:
        logger.error(f"❌ 导入过程出错: {e}", exc_info=True)
        importer.close_db()


if __name__ == "__main__":
    main()
