"""
生成股票列表JSON文件
从Qlib instruments数据生成前端可用的JSON格式
从PostgreSQL数据库读取股票名称
"""

import json
import os
from pathlib import Path
from typing import Dict

import psycopg2


def load_stock_names() -> Dict[str, str]:
    """
    从数据库加载股票名称映射
    """
    try:
        # 数据库连接配置
        db_config = {
            "host": os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT") or 5432),
            "database": os.getenv("DB_NAME", "quantmind"),
            "user": os.getenv("DB_USER", "quantmind"),
            "password": os.getenv("DB_PASSWORD", "admin123"),
        }

        print(
            f"📡 连接数据库: {db_config['host']}:{db_config['port']}/{db_config['database']}"
        )

        # 连接数据库
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        # 查询stock_snapshot表获取股票名称
        # 注意：表中的字段是 code 和 name，需要转换为标准格式的 symbol
        query = """
            SELECT DISTINCT code, name
            FROM stock_snapshot
            WHERE name IS NOT NULL
            AND name != ''
            AND code IS NOT NULL
            ORDER BY code
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        stock_names = {}
        for code, name in rows:
            # 转换格式: 000001 -> 000001.SZ, 600000 -> 600000.SH
            # 根据代码前缀判断市场
            if code.startswith("6") or code.startswith("5"):
                symbol = f"{code}.SH"
            elif code.startswith("0") or code.startswith("3"):
                symbol = f"{code}.SZ"
            elif code.startswith("4") or code.startswith("8"):
                symbol = f"{code}.BJ"
            else:
                # 其他情况，直接使用代码
                symbol = code

            stock_names[symbol] = name

        cursor.close()
        conn.close()

        print(f"✅ 从数据库加载 {len(stock_names)} 只股票名称")

        # 显示前5个示例
        if stock_names:
            print("📝 示例股票名称:")
            for i, (sym, nm) in enumerate(list(stock_names.items())[:5]):
                print(f"   {sym}: {nm}")

        return stock_names

    except Exception as e:
        print(f"⚠️  加载股票名称失败: {e}")
        print("   将生成不含名称的JSON文件")
        return {}


def generate_stocks_json():
    """生成stocks.json文件"""

    # 读取Qlib instruments数据
    qlib_data_path = Path("db/qlib_data/instruments/all.txt")

    if not qlib_data_path.exists():
        print(f"❌ 文件不存在: {qlib_data_path}")
        return

    print(f"📖 读取Qlib数据: {qlib_data_path}")

    # 加载股票名称（可选）
    stock_names = load_stock_names()

    stocks = []
    with open(qlib_data_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) >= 3:
                symbol_raw = parts[0]  # 如: SH600000
                parts[1]
                parts[2]

                # 格式转换: SH600000 -> 600000.SH
                if len(symbol_raw) >= 8:
                    market = symbol_raw[:2]  # SH, SZ, BJ
                    code = symbol_raw[2:]  # 600000
                    symbol = f"{code}.{market}"
                else:
                    symbol = symbol_raw
                    code = symbol_raw
                    market = ""

                # 剔除北交所
                if market == "BJ":
                    continue

                # 获取股票名称（如果有）
                name = stock_names.get(symbol, "")

                stock_info = {
                    "symbol": symbol,
                    "code": code,
                    "market": market,
                }

                # 只在有名称时添加name字段（减少文件大小）
                if name:
                    stock_info["name"] = name

                stocks.append(stock_info)

    print(f"✅ 成功读取 {len(stocks)} 只股票")

    # 生成JSON文件
    output_path = Path("electron/public/data/stocks.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1.0.0",
                "updated_at": "2026-01-14",
                "total": len(stocks),
                "stocks": stocks,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 计算文件大小
    file_size = output_path.stat().st_size
    file_size_kb = file_size / 1024

    print(f"📦 生成文件: {output_path}")
    print(f"📊 文件大小: {file_size_kb:.1f} KB")
    print(f"💡 Gzip压缩后预计: {file_size_kb * 0.2:.1f} KB")

    # 生成紧凑版本（不带缩进，进一步减小体积）
    compact_path = Path("electron/public/data/stocks.min.json")
    with open(compact_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1.0.0",
                "updated_at": "2026-01-14",
                "total": len(stocks),
                "stocks": stocks,
            },
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    compact_size = compact_path.stat().st_size
    compact_size_kb = compact_size / 1024

    print(f"📦 生成紧凑版: {compact_path}")
    print(f"📊 文件大小: {compact_size_kb:.1f} KB")

    # 显示示例数据
    print("\n📝 示例数据:")
    for stock in stocks[:5]:
        print(f"  {stock}")

    print("\n✅ 完成！")
    print("\n💡 使用方式:")
    print("  前端: fetch('/data/stocks.min.json')")
    print("  云端: 上传到CDN/OSS，定期更新")


if __name__ == "__main__":
    generate_stocks_json()
