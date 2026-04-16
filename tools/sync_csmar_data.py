import os
import duckdb
import pandas as pd
from datetime import datetime

# 配置
DB_PATH = 'db/csmar_data.duckdb'
RAW_BASE = 'db/csmar'

# 映射字典: 原始目录前缀 -> 数据库表名
TABLE_MAPPING = {
    '个股买卖不平衡指标表(日)': '个股买卖不平衡指标表日',
    '个股买卖价差表(日)': '个股买卖价差表日',
    '个股已实现指标表(日)': '个股已实现指标表日',
    '个股知情交易概率指标表(日)': '个股知情交易概率指标表日',
    '个股走势特征表': '个股走势特征表',
    '个股跳跃指标表(日)': '个股跳跃指标表日',
    '日个股回报率文件': '日个股回报率文件',
    '日市场规模统计': '日市场规模统计',
    '指数已实现指标表(日)': '指数已实现指标表日',
    '指数文件': '指数文件',
    '公司文件': '公司文件',
    '分配文件': '分配文件',
    '三因子模型指标(日)': '三因子模型指标日',
    '相对价值指标': '相对价值指标',
    '日交易统计文件': '日交易统计文件'
}

def get_latest_date(con, table_name, date_col):
    try:
        res = con.execute(f'SELECT MAX("{date_col}") FROM "{table_name}"').fetchone()[0]
        return res
    except:
        return None

def sync_table(con, raw_dir, table_name):
    print(f"\n>>> 正在同步表: {table_name} (来自 {raw_dir})...")
    
    raw_path = os.path.join(RAW_BASE, raw_dir)
    csv_file = next((f for f in os.listdir(raw_path) if f.endswith('.csv')), None)
    
    if not csv_file:
        print(f"    [跳过] 未在 {raw_dir} 中找到 CSV 文件。")
        return

    csv_path = os.path.join(raw_path, csv_file)
    
    # 1. 探测架构
    try:
        sample_df = pd.read_csv(csv_path, nrows=10)
    except Exception as e:
        print(f"    [错误] 无法读取 CSV: {e}")
        return

    # 找到时间列 (增加 SgnDate)
    date_col_raw = next((c for c in sample_df.columns if any(p in c.lower() for p in ['date', 'trddt', 'tradingdate', 'shrchgdt', 'accper', 'sgndate'])), None)
    
    if not date_col_raw:
        print(f"    [错误] 未能识别日期列。")
        return

    # 获取数据库中的日期列名 (增加 SgnDate)
    db_cols = [c[0] for c in con.execute(f'DESCRIBE "{table_name}"').fetchall()]
    date_col_db = next((c for c in ['date', 'TradingDate', 'Trddt', 'Shrchgdt', 'Accper', 'SgnDate'] if c in db_cols), None)
    
    if not date_col_db:
        print(f"    [错误] 未能在数据库表中识别日期列。")
        return

    # 2. 获取数据库最新日期
    latest_db_date = get_latest_date(con, table_name, date_col_db)
    print(f"    数据库当前最新日期: {latest_db_date}")

    # 3. 加载并过滤数据
    try:
        # 使用 chunksize 避免内存溢出 (虽然这里文件不大，但养成好习惯)
        all_new_data = []
        for chunk in pd.read_csv(csv_path, chunksize=50000):
            # 清洗脏数据 (处理掉可能混入的中文表头行)
            chunk = chunk[chunk[date_col_raw].astype(str).str.contains(r'\d{4}-\d{2}-\d{2}')]
            
            chunk[date_col_raw] = pd.to_datetime(chunk[date_col_raw], errors='coerce')
            chunk = chunk.dropna(subset=[date_col_raw])
            
            if latest_db_date:
                # 只保留更晚的数据
                # 如果 latest_db_date 是 string (来自 DuckDB)，转为 datetime
                if isinstance(latest_db_date, str):
                    latest_dt = pd.to_datetime(latest_db_date)
                else:
                    latest_dt = pd.Timestamp(latest_db_date)
                
                new_chunk = chunk[chunk[date_col_raw] > latest_dt]
            else:
                new_chunk = chunk
            
            if not new_chunk.empty:
                all_new_data.append(new_chunk)
        
        if not all_new_data:
            print(f"    [完成] 无需增量更新数据。")
            return

        final_df = pd.concat(all_new_data)
        
        # 4. 字段对齐
        # 简单将 CSV 列名映射到 DB 列名 (假设顺序或名称相似)
        # 这里我们尝试按名称对齐
        rename_map = {}
        for c in final_df.columns:
            if c in db_cols: continue
            # 模糊匹配
            for db_c in db_cols:
                if c.lower() == db_c.lower():
                    rename_map[c] = db_c
                    break
        
        final_df = final_df.rename(columns=rename_map)
        
        # 只保留 DB 中存在的列
        common_cols = [c for c in final_df.columns if c in db_cols]
        final_df = final_df[common_cols]
        
        # 5. 写入数据库
        # 使用 duckdb 的 register 机制快速导入 dataframe
        con.register('temp_frame', final_df)
        cols_str = ", ".join([f'"{c}"' for c in common_cols])
        con.execute(f'INSERT INTO "{table_name}" ({cols_str}) SELECT * FROM temp_frame')
        con.unregister('temp_frame')
        
        print(f"    [成功] 已同步 {len(final_df)} 条记录。")

    except Exception as e:
        print(f"    [异常] 同步过程中出错: {e}")

def main():
    print(f"=== CSMAR 数据增量同步工具 ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在 {DB_PATH}")
        return

    con = duckdb.connect(DB_PATH)
    
    # 扫描原始目录
    raw_dirs = [d for d in os.listdir(RAW_BASE) if os.path.isdir(os.path.join(RAW_BASE, d))]
    
    for raw_dir in raw_dirs:
        # 匹配表名
        matched_table = None
        for prefix, table in TABLE_MAPPING.items():
            if raw_dir.startswith(prefix):
                matched_table = table
                break
        
        if matched_table:
            sync_table(con, raw_dir, matched_table)
        else:
            print(f"\n[跳过] 未找到 {raw_dir} 的表映射。")

    con.close()
    print("\n=== 同步任务结束 ===")

if __name__ == "__main__":
    main()
