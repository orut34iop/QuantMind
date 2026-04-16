#!/usr/bin/env python3
"""
QuantMind 轻量级推理脚本 (Inference Only)
------------------------------------------
功能：加载已有模型文件（.txt/.pkl），在指定日期上运行预测，生成信号文件及配套元数据。
特点：不包含训练逻辑，执行速度快，适合每日盘后生成次日预测。
"""

import os
import sys
import json
import yaml
import argparse
import pickle
import pandas as pd
import lightgbm as lgb
from datetime import datetime, timedelta
from pathlib import Path
from qlib.utils import init_instance_by_config
import qlib

# 设置项目根目录
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

# 默认路径配置
DEFAULT_MODEL_DIR = ROOT / "models/production/model_qlib"
DEFAULT_CONFIG = DEFAULT_MODEL_DIR / "workflow_config.yaml"
DEFAULT_MODEL_TXT = DEFAULT_MODEL_DIR / "model.txt"
DEFAULT_DATA_DIR = ROOT / "db/qlib_data"

def load_pkl_with_compat(path):
    """兼容性加载 pickle 文件"""
    import numpy as np
    try:
        # 处理 numpy 兼容性（针对某些特定环境下的 pkl）
        patched = False
        if "numpy._core" not in sys.modules and hasattr(np, "core"):
            sys.modules["numpy._core"] = np.core
            patched = True
        
        with open(path, "rb") as f:
            return pickle.load(f)
    finally:
        if 'patched' in locals() and patched:
            if "numpy._core" in sys.modules:
                del sys.modules["numpy._core"]

def main():
    parser = argparse.ArgumentParser(description="QuantMind Inference Only Script")
    parser.add_argument("--date", type=str, help="预测日期 (YYYY-MM-DD)，默认为最新可得日期")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG), help="工作流配置文件路径")
    parser.add_argument("--model", type=str, default=str(DEFAULT_MODEL_TXT), help="模型文件路径（支持 .txt/.pkl）")
    parser.add_argument("--output_name", type=str, help="输出文件名预览 (不含扩展名)")
    
    args = parser.parse_args()

    # 1. 验证路径
    config_path = Path(args.config)
    model_path = Path(args.model)
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return 1
    if not model_path.exists():
        print(f"❌ 模型文件不存在: {model_path}")
        return 1

    # 2. 加载配置与初始化 Qlib
    print(f"📖 加载配置: {config_path.name}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    provider_uri = config.get("qlib_init", {}).get("provider_uri", str(DEFAULT_DATA_DIR))
    # 路径转换（处理 yaml 中可能的绝对路径）
    if "/home/ubuntu" in provider_uri: 
        provider_uri = str(DEFAULT_DATA_DIR)
        
    qlib.init(provider_uri=provider_uri, region="cn")
    print(f"✅ Qlib 已初始化: {provider_uri}")

    # 3. 加载模型
    print(f"🧠 加载模型: {model_path.name}")
    model_ext = model_path.suffix.lower()
    if model_ext == ".txt":
        model = lgb.Booster(model_file=str(model_path))
    elif model_ext == ".pkl":
        model = load_pkl_with_compat(model_path)
    else:
        print(f"❌ 不支持的模型格式: {model_ext}（仅支持 .txt/.pkl）")
        return 1

    # 4. 确定预测日期
    if args.date:
        prediction_date = args.date
    else:
        # 默认取日历中最后一天
        from qlib.data import D
        calendar = D.calendar()
        prediction_date = str(calendar[-1].date())
    
    print(f"🎯 预测日期设定为: {prediction_date}")

    # 5. 准备数据集 (Dataset)
    # 修改配置中的 segments 以仅包含预测日期
    dataset_config = config["task"]["dataset"]
    dataset_config["kwargs"]["segments"] = {
        "test": [prediction_date, prediction_date]
    }
    
    print("📋 正在准备数据特征...")
    dataset = init_instance_by_config(dataset_config)
    
    # 6. 执行推理
    print("🚀 开始推理内容...")
    try:
        if model_ext == ".txt":
            features = dataset.prepare("test", col_set="feature")
            if isinstance(features, tuple):
                features = features[0]
            pred_values = model.predict(features.values)
            pred = pd.DataFrame({"score": pred_values}, index=features.index)
        else:
            pred = model.predict(dataset, segment="test")
    except Exception as e:
        print(f"❌ 推理失败: {e}")
        # 常见原因为数据未对齐
        print("💡 建议：请确保已运行 daily_incremental_dump.py 同步最新数据。")
        return 1

    # 7. 格式化并保存结果
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    
    # 剔除北交所 (如有)
    if "instrument" in pred.index.names:
        inst = pred.index.get_level_values("instrument").astype(str).str.upper()
        pred = pred.loc[~inst.str.startswith("BJ")]

    # 生成文件名
    date_suffix = prediction_date.replace("-", "")
    base_name = args.output_name or f"pred_daily_{date_suffix}"
    out_pkl = DEFAULT_MODEL_DIR / f"{base_name}.pkl"
    out_meta = DEFAULT_MODEL_DIR / f"{base_name}.meta.json"

    print(f"💾 保存预测数据到: {out_pkl.name}")
    pred.to_pickle(out_pkl)

    # 8. 生成元数据文件 (供管理后台读取)
    meta = {
        "version": base_name,
        "model_path": str(model_path),
        "date_min": prediction_date,
        "date_max": prediction_date,
        "rows": len(pred),
        "instruments": int(pred.index.get_level_values("instrument").nunique()) if len(pred) else 0,
        "created_at": datetime.now().isoformat(),
        "output": str(out_pkl)
    }
    
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    print(f"✨ 流程完成！元数据已同步至: {out_meta.name}")
    print(f"📊 本次预测共覆盖 {meta['instruments']} 只股票。")
    return 0

if __name__ == "__main__":
    exit(main())
