#!/usr/bin/env python3
"""从alpha158_csvs填充OHLCV数据到训练数据集"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Fill OHLCV data from alpha158 CSVs")
    parser.add_argument("--year", type=int, default=2026, help="Year to process")
    parser.add_argument("--alpha-dir", default="db/alpha158_csvs", help="Alpha158 CSV directory")
    parser.add_argument("--train-dir", default="db/model_training_data", help="Training data directory")
    parser.add_argument("--output-dir", default="db/model_training_data", help="Output directory")
    return parser.parse_args()


def main():
    args = parse_args()
    
    alpha_dir = Path(args.alpha_dir)
    train_file = Path(args.train_dir) / f"train_ready_{args.year}.parquet"
    output_file = Path(args.output_dir) / f"train_ready_{args.year}.parquet"
    
    print(f"=== 填充 {args.year} 年 OHLCV 数据 ===")
    print(f"Alpha158目录: {alpha_dir}")
    print(f"训练数据: {train_file}")
    
    # 读取训练数据
    print("\n[1/4] 读取训练数据...")
    df_train = pd.read_parquet(train_file)
    print(f"  数据形状: {df_train.shape}")
    print(f"  当前OHLCV缺失情况:")
    for col in ['open', 'high', 'low', 'close', 'volume', 'factor']:
        null_count = df_train[col].isnull().sum()
        null_rate = null_count / len(df_train) * 100
        print(f"    {col}: {null_count:,} ({null_rate:.2f}%)")
    
    # 读取所有alpha158 CSV文件
    print("\n[2/4] 读取Alpha158 CSV文件...")
    csv_files = list(alpha_dir.glob("*.csv"))
    print(f"  找到 {len(csv_files):,} 个CSV文件")
    
    # 构建OHLCV数据字典
    print("\n[3/4] 构建OHLCV数据字典...")
    ohlcv_dict = {}
    
    for csv_file in tqdm(csv_files, desc="读取CSV"):
        try:
            symbol = csv_file.stem  # 文件名即股票代码
            df_csv = pd.read_csv(csv_file)
            df_csv['date'] = pd.to_datetime(df_csv['date']).dt.date  # 转换为date类型
            
            # 筛选目标年份
            df_year = df_csv[df_csv['date'].apply(lambda x: x.year if hasattr(x, 'year') else pd.Timestamp(x).year) == args.year].copy()
            
            if len(df_year) > 0:
                df_year['symbol'] = symbol
                ohlcv_dict[symbol] = df_year.set_index('date')
        except Exception as e:
            print(f"  警告: 读取 {csv_file.name} 失败: {e}")
    
    print(f"  成功读取 {len(ohlcv_dict):,} 只股票的OHLCV数据")
    
    # 填充OHLCV数据
    print("\n[4/4] 填充OHLCV数据...")
    filled_count = {'open': 0, 'high': 0, 'low': 0, 'close': 0, 'volume': 0, 'factor': 0}
    skipped_count = 0
    
    for idx in tqdm(df_train.index, desc="填充数据"):
        symbol = df_train.loc[idx, 'symbol']
        trade_date = df_train.loc[idx, 'trade_date']
        
        if symbol in ohlcv_dict:
            df_stock = ohlcv_dict[symbol]
            
            if trade_date in df_stock.index:
                row = df_stock.loc[trade_date]
                
                for col in ['open', 'high', 'low', 'close', 'volume', 'factor']:
                    if pd.isna(df_train.loc[idx, col]) and not pd.isna(row[col]):
                        df_train.loc[idx, col] = row[col]
                        filled_count[col] += 1
        else:
            skipped_count += 1
    
    print(f"\n填充统计:")
    for col, count in filled_count.items():
        print(f"  {col}: {count:,} 条")
    print(f"  跳过（无匹配CSV）: {skipped_count:,} 条")
    
    # 检查填充后的缺失情况
    print(f"\n填充后OHLCV缺失情况:")
    for col in ['open', 'high', 'low', 'close', 'volume', 'factor']:
        null_count = df_train[col].isnull().sum()
        null_rate = null_count / len(df_train) * 100
        print(f"  {col}: {null_count:,} ({null_rate:.2f}%)")
    
    # 保存结果
    print(f"\n保存到: {output_file}")
    df_train.to_parquet(output_file, index=False)
    print("完成！")
    
    # 更新报告
    report_file = Path(args.output_dir) / f"train_ready_{args.year}_report.json"
    if report_file.exists():
        import json
        with open(report_file, 'r') as f:
            report = json.load(f)
        
        # 更新填充率
        feature_cols = [c for c in df_train.columns if c not in ['symbol', 'trade_date', 'label']]
        null_stats = df_train[feature_cols].isnull().sum() / len(df_train)
        max_null_col = null_stats.idxmax()
        
        report['max_feature_null_ratio'] = float(null_stats[max_null_col])
        report['max_null_feature'] = max_null_col
        report['ohlcv_filled'] = filled_count
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"报告已更新: {report_file}")


if __name__ == "__main__":
    main()
