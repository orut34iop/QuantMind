"""
内存优化版 LightGBM 训练
适用于内存受限的环境（< 8GB）

优化策略：
1. 分批加载数据
2. 减少特征数量
3. 缩短时间范围
4. 使用内存高效的数据类型
"""

import gc
import pickle
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import qlib
from qlib.data import D
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error

warnings.filterwarnings("ignore")


def calculate_ic(predictions, labels):
    """计算信息系数 (IC)"""
    return np.corrcoef(predictions, labels)[0, 1]


def load_qlib_data_optimized(
    start_date, end_date, instruments=None, universe="csi300", max_instruments=100
):
    """
    内存优化的数据加载

    Args:
        start_date: 开始日期
        end_date: 结束日期
        instruments: 股票列表
        universe: 股票池
        max_instruments: 最大股票数量（限制内存）

    Returns:
        DataFrame with features
    """
    print("\n[1/7] 从 Qlib 加载数据（内存优化模式）...")
    print(f"  时间范围: {start_date} ~ {end_date}")
    print(f"  最大股票数: {max_instruments}")

    # 获取股票列表
    if instruments is None:
        all_instruments = D.instruments(market=universe)
        # 限制股票数量以节省内存
        if len(all_instruments) > max_instruments:
            print(
                f"  ⚠️  股票池有 {len(all_instruments)} 只，限制为前 {max_instruments} 只"
            )
            instruments = all_instruments[:max_instruments]
        else:
            instruments = all_instruments

    print(f"  实际使用: {len(instruments)} 只股票")

    # 简化特征：只使用最重要的 7 个特征
    features = [
        "($close - Ref($close, 1)) / Ref($close, 1)",  # returns (最重要)
        "Mean($close, 5) / $close - 1",  # ma5_ratio
        "Mean($close, 20) / $close - 1",  # ma20_ratio
        "Std($close, 20)",  # volatility_20
        "$volume / Mean($volume, 20)",  # volume_ratio
        "($close - $open) / $open",  # intraday_return
        "($high - $low) / $open",  # intraday_range
    ]

    feature_names = [
        "returns",
        "ma5_ratio",
        "ma20_ratio",
        "volatility_20",
        "volume_ratio",
        "intraday_return",
        "intraday_range",
    ]

    # 标签：未来1日收益
    label = "Ref($close, -1) / $close - 1"

    print(f"  特征数量: {len(features)} (已优化)")
    print("  开始加载...")

    # 一次性加载所有数据
    all_exprs = features + [label]
    data = D.features(
        instruments,
        all_exprs,
        start_time=start_date,
        end_time=end_date,
    )

    # 重命名列
    data.columns = feature_names + ["label"]

    # 删除缺失值
    original_len = len(data)
    data = data.dropna()
    print(f"  加载完成: {len(data)} 条记录 (删除 {original_len - len(data)} 条缺失)")

    # 转换为内存高效的数据类型
    for col in data.columns:
        if data[col].dtype == "float64":
            data[col] = data[col].astype("float32")

    print(f"  内存占用: {data.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")

    return data, feature_names


def prepare_train_valid_test_optimized(df, feature_names, train_end, valid_end):
    """内存优化的数据划分"""
    print("\n[2/7] 划分数据集...")

    # 获取日期索引
    dates = df.index.get_level_values("datetime")

    # 划分
    train_mask = dates <= train_end
    valid_mask = (dates > train_end) & (dates <= valid_end)
    test_mask = dates > valid_end

    # 直接提取 numpy 数组，不保留 DataFrame（节省内存）
    X_train = df.loc[train_mask, feature_names].values.astype("float32")
    y_train = df.loc[train_mask, "label"].values.astype("float32")

    X_valid = df.loc[valid_mask, feature_names].values.astype("float32")
    y_valid = df.loc[valid_mask, "label"].values.astype("float32")

    X_test = df.loc[test_mask, feature_names].values.astype("float32")
    y_test = df.loc[test_mask, "label"].values.astype("float32")

    # 保存测试集的索引（用于生成 pred.pkl）
    test_index = df[test_mask].index

    print(f"  训练集: {X_train.shape}")
    print(f"  验证集: {X_valid.shape}")
    print(f"  测试集: {X_test.shape}")

    # 立即删除原始 DataFrame 释放内存
    del df
    gc.collect()
    print("  ✅ 已释放原始数据内存")

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_valid": X_valid,
        "y_valid": y_valid,
        "X_test": X_test,
        "y_test": y_test,
        "test_index": test_index,
        "feature_names": feature_names,
    }


def train_lightgbm_model_optimized(dataset):
    """训练 LightGBM 模型（内存优化）"""
    print("\n[3/7] 训练 LightGBM 模型（内存优化）...")

    model = LGBMRegressor(
        objective="regression",
        num_leaves=20,  # 减少 (默认31)
        learning_rate=0.05,
        n_estimators=100,  # 减少 (默认200)
        max_depth=5,  # 减少 (默认7)
        min_child_samples=30,  # 增加 (默认20)
        subsample=0.7,  # 减少 (默认0.8)
        colsample_bytree=0.7,  # 减少 (默认0.8)
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        n_jobs=2,  # 限制CPU使用 (默认-1)
        verbose=-1,
    )

    model.fit(
        dataset["X_train"],
        dataset["y_train"],
        eval_set=[(dataset["X_valid"], dataset["y_valid"])],
        eval_metric="l2",
    )

    print("  ✅ 模型训练完成")

    # 立即释放训练数据
    del dataset["X_train"], dataset["y_train"]
    gc.collect()

    return model


def evaluate_model_optimized(model, dataset):
    """评估模型性能"""
    print("\n[4/7] 评估模型性能...")

    # 只评估验证集和测试集（跳过训练集节省时间）
    valid_pred = model.predict(dataset["X_valid"])
    valid_ic = calculate_ic(valid_pred, dataset["y_valid"])

    test_pred = model.predict(dataset["X_test"])
    test_mse = mean_squared_error(dataset["y_test"], test_pred)
    test_ic = calculate_ic(test_pred, dataset["y_test"])

    print(f"\n  验证集 IC:  {valid_ic:.4f}")
    print(f"  测试集 IC:  {test_ic:.4f}")
    print(f"  测试集 MSE: {test_mse:.6f}")

    return {
        "valid_ic": valid_ic,
        "test_ic": test_ic,
        "test_mse": test_mse,
    }


def generate_predictions_optimized(model, dataset):
    """生成预测（只生成测试集）"""
    print("\n[5/7] 生成预测（仅测试集）...")

    # 只预测测试集（不预测训练集和验证集以节省内存）
    test_pred = model.predict(dataset["X_test"])

    # 创建 pred.pkl 格式的 DataFrame
    pred_df = pd.DataFrame({"score": test_pred}, index=dataset["test_index"])

    print(f"  预测数量: {len(pred_df)}")
    print(
        f"  日期范围: {pred_df.index.get_level_values('datetime').min()} ~ {pred_df.index.get_level_values('datetime').max()}"
    )
<<<<<<< HEAD
    print(f"  股票数量: {len(pred_df.index.get_level_values('instrument').unique())}")
    print(f"  得分范围: [{pred_df['score'].min():.6f}, {pred_df['score'].max():.6f}]")
=======
    print(
        f"  股票数量: {len(pred_df.index.get_level_values('instrument').unique())}")
    print(
        f"  得分范围: [{pred_df['score'].min():.6f}, {pred_df['score'].max():.6f}]")
>>>>>>> refactor/service-cleanup

    # 释放测试数据
    del dataset["X_test"], dataset["y_test"]
    gc.collect()

    return pred_df


def save_model_and_predictions(model, pred_df, metrics, feature_names, output_dir):
    """保存模型和预测结果"""
    print("\n[6/7] 保存模型和结果...")

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = Path(output_dir) / f"lightgbm_csi300_lite_{timestamp}"
    model_dir.mkdir(parents=True, exist_ok=True)

    # 保存模型
    model_path = model_dir / "model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  ✅ 模型: {model_path}")

    # 保存元数据
    metadata = {
        "model_type": "LightGBM (Memory Optimized)",
        "timestamp": timestamp,
        "features": feature_names,
        "metrics": metrics,
        "num_predictions": len(pred_df),
        "date_range": [
            str(pred_df.index.get_level_values("datetime").min()),
            str(pred_df.index.get_level_values("datetime").max()),
        ],
    }
    metadata_path = model_dir / "metadata.json"
    import json

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✅ 元数据: {metadata_path}")

    # 保存 pred.pkl
    pred_path = model_dir / "pred.pkl"
    with open(pred_path, "wb") as f:
        pickle.dump(pred_df, f)
    print(f"  ✅ 预测结果: {pred_path}")

    # 特征重要性
    feature_importance = pd.DataFrame(
        {"feature": feature_names, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    importance_path = model_dir / "feature_importance.csv"
    feature_importance.to_csv(importance_path, index=False)
    print(f"  ✅ 特征重要性: {importance_path}")

    print("\n  📊 Top 3 重要特征:")
    for idx, row in feature_importance.head(3).iterrows():
        print(f"    {row['feature']:20s}: {row['importance']:.4f}")

    return model_dir, pred_path


def main():
    """主流程"""
    print("=" * 80)
    print("LightGBM 训练流程（内存优化版）")
    print("=" * 80)
    print("\n⚡ 优化策略:")
    print("  • 限制股票数量: 100只 (可调整)")
    print("  • 简化特征: 7个核心特征")
    print("  • 缩短时间: 2023-2024 (2年)")
    print("  • 模型参数: 降低复杂度")
    print("  • 数据类型: float32")
    print("  • 及时释放: 主动垃圾回收")

    # 配置参数
    QLIB_DATA_PATH = "E:/code/quantmind/research/data_adapter/qlib_data"
    OUTPUT_DIR = "../../models/candidates"

    # 时间划分（缩短以节省内存）
    START_DATE = "2023-01-01"  # 从2023开始（不是2020）
    TRAIN_END = "2023-09-30"  # 训练集：9个月
    VALID_END = "2023-12-31"  # 验证集：3个月
    END_DATE = "2024-12-31"  # 测试集：12个月

    UNIVERSE = "csi300"
    MAX_INSTRUMENTS = 100  # 限制最大股票数量

    # 初始化 Qlib
    print("\n[0/7] 初始化 Qlib...")
    qlib.init(provider_uri=QLIB_DATA_PATH, region="cn")
    print(f"  ✅ Qlib 数据路径: {QLIB_DATA_PATH}")

    # 加载数据
    df, feature_names = load_qlib_data_optimized(
        START_DATE,
        END_DATE,
        instruments=None,
        universe=UNIVERSE,
        max_instruments=MAX_INSTRUMENTS,
    )

    # 划分数据集
    dataset = prepare_train_valid_test_optimized(
        df, feature_names, TRAIN_END, VALID_END
    )

    # 训练模型
    model = train_lightgbm_model_optimized(dataset)

    # 评估性能
    metrics = evaluate_model_optimized(model, dataset)

    # 生成预测
    pred_df = generate_predictions_optimized(model, dataset)

    # 保存
    model_dir, pred_path = save_model_and_predictions(
        model, pred_df, metrics, feature_names, OUTPUT_DIR
    )

    print("\n[7/7] 复制 pred.pkl 到工作目录...")
    import shutil

    target_pred_path = Path("E:/code/quantmind/research/data_adapter/pred.pkl")
    shutil.copy(pred_path, target_pred_path)
    print(f"  ✅ 已复制到: {target_pred_path}")

    # 完成
    print("\n" + "=" * 80)
    print("✅ 训练完成！")
    print("=" * 80)
    print(f"\n📁 模型目录: {model_dir}")
    print(f"📊 测试集 IC: {metrics['test_ic']:.4f}")
    print(f"📈 预测数量: {len(pred_df)}")
    print("\n💡 提示:")
    print("  • 如果需要更多股票，调整 MAX_INSTRUMENTS")
    print("  • 如果需要更长时间，调整 START_DATE")
    print("  • 当前配置适合 4-8GB 内存")
    print("=" * 80)


if __name__ == "__main__":
    main()
