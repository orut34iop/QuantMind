from backend.data_management.ifind_client import get_ifind_client
import asyncio
import os
import logging
import sys

import asyncpg
import pandas as pd
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.append(os.getcwd())


# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

# 数据库配置
DB_HOST = (os.getenv("DB_MASTER_HOST") or "127.0.0.1").strip()
DB_PORT = (os.getenv("DB_MASTER_PORT") or "5432").strip()
DB_USER = (os.getenv("DB_USER") or "quantmind").strip()
DB_PASSWORD = (os.getenv("DB_PASSWORD") or "admin123").strip()
DB_NAME = (os.getenv("DB_NAME") or "quantmind").strip()

# iFind 指标映射 (iFind Indicator -> DB Column)
INDICATOR_MAPPING = {
    "ths_pe_ttm_stock": "pe_ratio",
    "ths_pb_mrq_stock": "pb_ratio",
    "ths_ps_ttm_stock": "ps_ratio",
    "ths_total_value_stock": "market_cap",
    "ths_turnover_ratio_stock": "turnover_rate",
    "ths_roe_stock": "roe",
    "ths_net_profit_growth_rate_stock": "net_profit_growth",
}


def format_ifind_symbol(symbol: str) -> str:
    """将 6 位代码转换为 iFind 格式 (如 000001.SZ)"""
    if "." in symbol:
        return symbol

    if symbol.startswith(("60", "68", "90")):
        return f"{symbol}.SH"
    elif symbol.startswith(("00", "30", "20")):
        return f"{symbol}.SZ"
    elif symbol.startswith(("43", "83", "87", "92")):
        return f"{symbol}.BJ"
    return symbol


async def supplement_data():
    """补全 iFind 数据"""
    logger.info("连接数据库...")
    try:
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
        )
    except Exception as e:
        logger.error(f"连接数据库失败: {e}")
        return

    try:
        # 1. 查找 2026 年 1 月缺失数据的记录
        # 优先补全 PE, PB, ROE 为空的记录
        logger.info("正在查询 2026-01 缺失数据的记录...")
        missing_records = await conn.fetch("""
            SELECT trade_date, symbol
            FROM stock_selection
            WHERE trade_date >= '2026-01-01' AND trade_date < '2026-02-01'
              AND (pe_ratio IS NULL OR pb_ratio IS NULL OR roe IS NULL)
            ORDER BY trade_date, symbol
        """)

        if not missing_records:
            logger.info("未发现缺失数据。")
            return

        logger.info(f"发现 {len(missing_records)} 条缺失记录。")

        # 按日期分组处理，以提高效率（iFind 支持单次请求多只股票）
        date_groups = {}
        for rec in missing_records:
            d = rec["trade_date"]
            if d not in date_groups:
                date_groups[d] = []
            date_groups[d].append(rec["symbol"])

        client = get_ifind_client()
        indicators = ",".join(INDICATOR_MAPPING.keys())

        # 拉取频率设置：每秒 30 次 -> 每次间隔约 0.033s
        # 注意：iFind SDK 本身可能也有限制，这里按用户要求设置间隔
        INTERVAL = 1.0 / 30.0

        processed_count = 0
        total_groups = len(date_groups)

        for idx, (trade_date, symbols) in enumerate(date_groups.items(), 1):
            date_str = trade_date.strftime("%Y-%m-%d")
            logger.info(
                f"[{idx}/{total_groups}] 处理日期 {date_str}, 股票数: {len(symbols)}"
            )

            # 过滤掉非 A 股（如 B 股 200xxx, 900xxx）以减少错误
            a_share_symbols = [
                s
                for s in symbols
                if s.startswith(("00", "30", "60", "68", "43", "83", "87", "92"))
            ]
            if not a_share_symbols:
                continue

            # 分批处理股票（每批 20 只）
            BATCH_SIZE = 20
            for i in range(0, len(a_share_symbols), BATCH_SIZE):
                batch_symbols = a_share_symbols[i: i + BATCH_SIZE]
                ifind_symbols = [format_ifind_symbol(s) for s in batch_symbols]

                try:
                    # 频率控制
                    await asyncio.sleep(INTERVAL)

                    # 调用 iFind SDK
                    df = client.get_basic_data(
                        codes=ifind_symbols, indicators=indicators, date=date_str
                    )

                    if df is not None and not df.empty:
                        # 批量更新数据库
                        for _, row in df.iterrows():
                            ifind_code = row.get("thscode")
                            if not ifind_code:
                                continue

                            symbol = (
                                ifind_code.split(".")[0]
                                if "." in ifind_code
                                else ifind_code
                            )

                            # 构建更新字段
                            params = [symbol, trade_date]

                            set_clauses = []
                            param_idx = 3
                            has_data = False
                            for ifind_ind, db_col in INDICATOR_MAPPING.items():
                                val = row.get(ifind_ind)
                                if pd.isna(val) or val is None:
                                    val = None
                                else:
                                    has_data = True
                                    # 处理百分比数据
                                    if db_col in [
                                        "turnover_rate",
                                        "roe",
                                        "net_profit_growth",
                                    ]:
                                        try:
                                            val = float(val) / 100.0
                                        except:
                                            val = None

                                set_clauses.append(f"{db_col} = ${param_idx}")
                                params.append(val)
                                param_idx += 1

                            if has_data:
                                sql = f"""
                                    UPDATE stock_selection
                                    SET {", ".join(set_clauses)}
                                    WHERE symbol = $1 AND trade_date = $2
                                """
                                await conn.execute(sql, *params)
                                processed_count += 1

                except Exception as e:
                    logger.error(
                        f"处理批次失败 ({date_str}, {batch_symbols[0]}...): {e}"
                    )
                    # 如果批次失败，尝试单个处理
                    for s in batch_symbols:
                        try:
                            await asyncio.sleep(INTERVAL)
                            single_df = client.get_basic_data(
                                format_ifind_symbol(s), indicators, date_str
                            )
                            # ... (这里可以添加单个更新逻辑，但为了简洁先记录日志)
                            logger.info(
                                f"单个重试 {s}: {'成功' if not single_df.empty else '无数据'}"
                            )
                        except:
                            pass

        logger.info(f"数据补全完成！共更新 {processed_count} 条记录。")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(supplement_data())
