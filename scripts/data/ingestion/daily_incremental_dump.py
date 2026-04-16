#!/usr/bin/env python3
"""
QuantMind 增量数据入库工具 (CSV -> Qlib Bin)
------------------------------------------
功能：每日收盘后，将 /data 下各股票的 48 维特征追加到 Qlib 二进制文件中。
设计：
1. 扫描 DATA_DIR 下的 .csv 文件。
2. 自动检测特征列并对应到 features/<instrument>/<feature>.day.bin。
3. 更新 calendars/day.txt。
4. 更新 instruments/*.txt 的结束日期。
5. 提供备份与回滚能力。
"""

import os
import sys
import shutil
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# 配置路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
QLIB_DATA_DIR = PROJECT_ROOT / "db" / "qlib_data" / "day"
ARCHIVE_DIR = DATA_DIR / "archive"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "logs" / "data_ingestion.log")
    ]
)
logger = logging.getLogger("DataIngestion")

def backup_file(file_path: Path):
    """备份文件，增加时间戳后缀"""
    if file_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".bak_{timestamp}")
        shutil.copy2(file_path, backup_path)
        return backup_path
    return None

def update_calendar(new_date_str: str):
    """更新 Qlib 日历文件"""
    calendar_path = QLIB_DATA_DIR / "calendars" / "day.txt"
    if not calendar_path.exists():
        logger.error(f"日历文件不存在: {calendar_path}")
        return False

    with open(calendar_path, "r") as f:
        existing_dates = [line.strip() for line in f.readlines()]

    if new_date_str in existing_dates:
        logger.warning(f"日期 {new_date_str} 已存在于日历中，跳过日历更新")
        return True

    backup_file(calendar_path)
    with open(calendar_path, "a") as f:
        f.write(f"{new_date_str}\n")
    logger.info(f"已将日期 {new_date_str} 追加到日历")
    return True

def update_instruments(new_date_str: str):
    """更新所有 instruments 索引文件的结束日期"""
    instr_dir = QLIB_DATA_DIR / "instruments"
    updated_count = 0
    for txt_file in instr_dir.glob("*.txt"):
        if ".bak_" in txt_file.name:
            continue
        
        backup_file(txt_file)
        lines = []
        with open(txt_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    # 格式: SYMBOL START_DATE END_DATE
                    # 将 END_DATE 替换为新日期
                    parts[2] = new_date_str
                    lines.append("	".join(parts))
                else:
                    lines.append(line.strip())
        
        with open(txt_file, "w") as f:
            f.write("\n".join(lines) + "\n")
        updated_count += 1
    
    logger.info(f"已更新 {updated_count} 个索引文件的结束日期至 {new_date_str}")

def process_stock_csv(csv_path: Path, new_date_str: str):
    """处理单个股票的 CSV 并追加二进制数据"""
    try:
        instrument = csv_path.stem.lower() # 假设文件名为 SH600036.csv
        df = pd.read_csv(csv_path)
        
        # 验证日期
        if 'date' in df.columns:
            csv_date = str(pd.to_datetime(df['date'].iloc[0]).date())
            if csv_date != new_date_str:
                logger.error(f"文件 {csv_path.name} 日期 ({csv_date}) 与预期 ({new_date_str}) 不符")
                return False
        
        # 确定特征目录
        feature_base_dir = QLIB_DATA_DIR / "features" / instrument
        if not feature_base_dir.exists():
            # logger.warning(f"特征目录不存在，跳过股票: {instrument}")
            # 如果目录不存在，可能需要根据 all.txt 创建，但增量模式下通常认为已存在
            return False

        # 遍历 DataFrame 列并匹配 .day.bin
        # 排除 date, instrument 等元数据列
        feature_cols = [c for c in df.columns if c.lower() not in ('date', 'instrument', 'symbol')]
        
        appended_features = 0
        for col in feature_cols:
            bin_file = feature_base_dir / f"{col.lower()}.day.bin"
            if bin_file.exists():
                val = float(df[col].iloc[0])
                # 以 float32 追加
                with open(bin_file, "ab") as f:
                    f.write(np.float32(val).tobytes())
                appended_features += 1
        
        return appended_features > 0
    except Exception as e:
        logger.error(f"处理 {csv_path.name} 失败: {e}")
        return False

def main():
    logger.info("开始执行增量数据入库流程...")
    
    # 1. 检查是否有新数据
    csv_files = list(DATA_DIR.glob("*.csv"))
    if not csv_files:
        logger.info("未发现待处理的 CSV 文件。")
        return

    # 2. 确定本次入库的日期 (以第一个文件为准)
    try:
        sample_df = pd.read_csv(csv_files[0])
        if 'date' not in sample_df.columns:
            logger.error("CSV 文件必须包含 'date' 列")
            return
        new_date_str = str(pd.to_datetime(sample_df['date'].iloc[0]).date())
    except Exception as e:
        logger.error(f"解析日期失败: {e}")
        return

    logger.info(f"检测到新日期: {new_date_str}，准备入库 {len(csv_files)} 只股票的数据")

    # 3. 更新系统元数据
    if not update_calendar(new_date_str):
        logger.error("日历更新失败，流程终止。")
        return
    
    update_instruments(new_date_str)

    # 4. 遍历处理每个股票
    success_count = 0
    for csv_file in csv_files:
        if process_stock_csv(csv_file, new_date_str):
            success_count += 1
            # 处理完移动到 archive
            ARCHIVE_DIR.mkdir(exist_ok=True)
            shutil.move(str(csv_file), str(ARCHIVE_DIR / csv_file.name))

    logger.info(f"入库完成：成功处理 {success_count}/{len(csv_files)} 只股票。")
    logger.info("提示：请手动重启 quantmind-engine 服务或触发模型重新加载以刷新数据。")

if __name__ == "__main__":
    main()
