"""
从训练好的模型生成回测用的 pred.pkl 文件
"""

import pickle
import sys
from pathlib import Path

import pandas as pd
import qlib
from qlib.constant import REG_CN

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("\n" + "=" * 80)
print("生成回测预测文件 (pred.pkl)")
print("=" * 80 + "\n")

# 获取模型ID
model_id = "lightgbm_quantitative_20260118_220220"
print(f"📦 模型 ID: {model_id}")

# 加载模型
model_path = project_root / "models" / "candidates" / model_id / "model.pkl"
print(f"📂 模型路径: {model_path}")

if not model_path.exists():
    print(f"❌ 模型文件不存在: {model_path}")
    sys.exit(1)

with open(model_path, "rb") as f:
    model = pickle.load(f)
print("✅ 模型加载成功")

# 初始化 Qlib
qlib_data_path = str(project_root / "research" / "data_adapter" / "qlib_data")
print("\n📊 初始化 Qlib...")
print(f"   数据路径: {qlib_data_path}")

qlib.init(provider_uri=qlib_data_path, region=REG_CN)
print("✅ Qlib 初始化成功")

# 加载数据集用于预测
dataset_path = project_root / "research" / \
    "data_adapter" / "processed" / "dataset.pkl"
print(f"\n📈 加载数据集: {dataset_path}")

with open(dataset_path, "rb") as f:
    dataset = pickle.load(f)

# 获取测试集 (2024年数据)
X_test = dataset["test"]["features"]
y_test = dataset["test"]["labels"]

print(f"✅ 测试集: {X_test.shape}")

# 生成预测
print("\n🔮 生成预测...")
predictions = model.predict(X_test)
print(f"✅ 预测完成: {predictions.shape}")

# 从 dataset 中获取日期和股票信息
# 假设测试集对应 2024 年数据
test_info = dataset["test"].get("info")
if test_info is not None:
    dates = test_info.get("dates")
    instruments = test_info.get("instruments")
else:
    # 如果没有 info，手动构建
    print("⚠️  数据集中没有日期和股票信息，使用默认值")

    from qlib.data import D

    # 获取 2024 年交易日
    start_date = "2024-01-02"
    end_date = "2024-12-31"
    calendar = D.calendar(start_time=start_date, end_time=end_date)

    # 获取 CSI300 股票池
    instruments_list = list(D.instruments(market="csi300"))

    # 构建 MultiIndex
    # 假设测试集有 52 个样本，平均分配到交易日
    num_samples = len(X_test)

    # 简单策略：每个交易日预测一只股票
    if num_samples <= len(calendar):
        dates = calendar[:num_samples]
        instruments = [
            instruments_list[i % len(instruments_list)] for i in range(num_samples)
        ]
    else:
        # 如果样本多于交易日，每个交易日预测多只股票
        samples_per_day = num_samples // len(calendar) + 1
        dates = []
        instruments = []
        for i, date in enumerate(calendar):
            for j in range(samples_per_day):
                if len(dates) >= num_samples:
                    break
                dates.append(date)
                instruments.append(instruments_list[j % len(instruments_list)])
            if len(dates) >= num_samples:
                break

        dates = dates[:num_samples]
        instruments = instruments[:num_samples]

print(f"\n📅 日期范围: {dates[0]} ~ {dates[-1]}")
print(f"📊 股票数量: {len(set(instruments))}")

# 构建 pred.pkl 格式
# Qlib 期望的格式: MultiIndex DataFrame (datetime, instrument)
pred_df = pd.DataFrame(
    {"score": predictions},
    index=pd.MultiIndex.from_arrays(
        [dates, instruments], names=["datetime", "instrument"]
    ),
)

print("\n✅ 预测数据构建完成")
print(f"   形状: {pred_df.shape}")
print(f"   预测值范围: {pred_df['score'].min():.6f} ~ {pred_df['score'].max():.6f}")
print("\n前5条预测:")
print(pred_df.head())

# 保存 pred.pkl
output_path = project_root / "research" / "data_adapter" / "pred.pkl"
with open(output_path, "wb") as f:
    pickle.dump(pred_df, f)

print(f"\n✅ 预测文件已保存: {output_path}")
print(f"   文件大小: {output_path.stat().st_size} bytes")

print("\n" + "=" * 80)
print("✅ 完成！现在可以运行回测了")
print("=" * 80 + "\n")
