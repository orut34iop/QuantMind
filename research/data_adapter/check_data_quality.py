"""
数据质量检查和统计报告
"""

from pathlib import Path

import pandas as pd


def check_data_quality(file_path):
    """检查单个文件的数据质量"""
    df = pd.read_csv(file_path)

    report = {
        "file": file_path.name,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "date_range": f"{df['date'].min()} 至 {df['date'].max()}",
        "missing_values": df.isnull().sum().to_dict(),
        "price_stats": {
            "close_mean": df["close"].mean(),
            "close_std": df["close"].std(),
            "close_min": df["close"].min(),
            "close_max": df["close"].max(),
        },
        "volume_stats": {
            "volume_mean": df["volume"].mean(),
            "volume_std": df["volume"].std(),
        },
    }

    # 检查异常值
    issues = []

    # 价格异常 (high < low 或 close > high 或 close < low)
    if (df["high"] < df["low"]).any():
        issues.append("发现 high < low 的异常数据")
    if (df["close"] > df["high"]).any():
        issues.append("发现 close > high 的异常数据")
    if (df["close"] < df["low"]).any():
        issues.append("发现 close < low 的异常数据")

    # 价格为0或负数
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        issues.append("发现价格<=0的异常数据")

    # 成交量为0
    zero_volume = (df["volume"] == 0).sum()
    if zero_volume > 0:
        issues.append(f"发现 {zero_volume} 天成交量为0")

    report["issues"] = issues
    return report


def main():
    print("=" * 80)
    print("数据质量检查报告")
    print("=" * 80)

    data_dir = Path("raw/1d")
    if not data_dir.exists():
        print(f"✗ 目录不存在: {data_dir}")
        return

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print("✗ 未找到CSV文件")
        return

    print(f"\n检查 {len(csv_files)} 个文件...\n")

    all_reports = []

    for csv_file in csv_files:
        try:
            report = check_data_quality(csv_file)
            all_reports.append(report)

            # 显示报告
            print(f"📊 {report['file']}")
            print(f"   数据行数: {report['rows']}")
            print(f"   日期范围: {report['date_range']}")
            print(
                f"   价格统计: 均值={report['price_stats']['close_mean']:.2f}, "
                f"最小={report['price_stats']['close_min']:.2f}, "
                f"最大={report['price_stats']['close_max']:.2f}"
            )

            # 缺失值
            missing = sum(report["missing_values"].values())
            if missing > 0:
                print(f"   ⚠️  缺失值: {missing}")

            # 问题
            if report["issues"]:
                print("   ⚠️  问题:")
                for issue in report["issues"]:
                    print(f"      - {issue}")
            else:
                print("   ✓ 数据质量良好")

            print()

        except Exception as e:
            print(f"✗ {csv_file.name}: 检查失败 - {e}\n")

    # 汇总统计
    print("=" * 80)
    print("汇总统计")
    print("=" * 80)

    total_rows = sum(r["rows"] for r in all_reports)
    total_issues = sum(len(r["issues"]) for r in all_reports)

    print(f"\n总文件数: {len(all_reports)}")
    print(f"总数据行: {total_rows:,}")
    print(f"平均每股: {total_rows // len(all_reports)} 个交易日")
    print(f"发现问题: {total_issues} 个")

    if total_issues == 0:
        print("\n✓ 所有数据质量良好，可以用于模型训练！")
    else:
        print("\n⚠️  发现一些数据质量问题，建议清洗后使用")

    # 价格范围统计
    print("\n价格范围:")
    price_stats = pd.DataFrame([r["price_stats"] for r in all_reports])
    print(f"  最低价: {price_stats['close_min'].min():.2f} 元")
    print(f"  最高价: {price_stats['close_max'].max():.2f} 元")
    print(f"  平均价: {price_stats['close_mean'].mean():.2f} 元")

    # 成交量统计
    print("\n成交量范围:")
    volume_stats = pd.DataFrame([r["volume_stats"] for r in all_reports])
    print(f"  平均成交量: {volume_stats['volume_mean'].mean():,.0f} 股")

    # 日期覆盖
    all_dates = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        all_dates.extend(df["date"].tolist())

    unique_dates = sorted(set(all_dates))
    print("\n时间覆盖:")
    print(f"  开始日期: {unique_dates[0]}")
    print(f"  结束日期: {unique_dates[-1]}")
    print(f"  交易日数: {len(unique_dates)}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
