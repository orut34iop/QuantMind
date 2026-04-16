"""
完整数据集训练流程 - LightGBM
从 Qlib 数据生成特征 → 训练模型 → 生成 pred.pkl

支持使用真实的 CSI300 成分股数据
"""

import os
import pickle
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import qlib
from qlib.config import C
from qlib.data import D
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def calculate_ic(predictions, labels):
    """计算信息系数 (IC)"""
    return np.corrcoef(predictions, labels)[0, 1]


def load_qlib_data(start_date, end_date, instruments=None, universe="csi300"):
    """
    从 Qlib 加载数据并生成特征

    Args:
        start_date: 开始日期
        end_date: 结束日期
        instruments: 股票列表（可选）
        universe: 股票池（如果 instruments 为空）

    Returns:
        DataFrame with features
    """
    print("\n[1/7] 从 Qlib 加载数据...")
    print(f"  时间范围: {start_date} ~ {end_date}")
    print(
        f"  股票池: {universe if not instruments else f'{len(instruments)} 只股票'}")

    # 获取股票配置（Qlib 会自动解析）
    if instruments is None:
        instruments = D.instruments(market=universe)

    # 注意：instruments 可能是配置字典，不是列表
    # 实际股票数量需要在数据加载后才能确定

    # 定义特征表达式
    features = [
        "($close / $open - 1)",  # close_open_ratio
        "($high / $low - 1)",  # high_low_ratio
        "Ref($close, 1)",  # 前一日收盘价
        "($close - Ref($close, 1)) / Ref($close, 1)",  # returns
        "Mean($close, 5)",  # ma5
        "Mean($close, 10)",  # ma10
        "Mean($close, 20)",  # ma20
        "Std($close, 5)",  # volatility_5
        "Std($close, 10)",  # volatility_10
        "$close",
        "$open",
        "$high",
        "$low",
        "$volume",
    ]

    # 标签：未来1日收益
    label = "Ref($close, -1) / $close - 1"

    # 加载数据
    data = {}
    for feature_expr in features + [label]:
        field_data = D.features(
            instruments,
            [feature_expr],
            start_time=start_date,
            end_time=end_date,
        )

        # 去掉 feature 列的前缀（如 'feature_0'）
        if len(field_data.columns) == 1:
            col_name = field_data.columns[0]
            data[col_name] = field_data[col_name]

    df = pd.DataFrame(data)

    # 重命名列
    feature_names = [
        "close_open_ratio",
        "high_low_ratio",
        "prev_close",
        "returns",
        "ma5",
        "ma10",
        "ma20",
        "volatility_5",
        "volatility_10",
        "close",
        "open",
        "high",
        "low",
        "volume",
    ]

    # 获取实际的列名并重命名
    actual_cols = df.columns.tolist()
    rename_dict = {}
    for i, name in enumerate(feature_names):
        if i < len(actual_cols) - 1:  # 最后一列是 label
            rename_dict[actual_cols[i]] = name
    rename_dict[actual_cols[-1]] = "label"

    df = df.rename(columns=rename_dict)

    # 删除缺失值
    df = df.dropna()

    # 获取实际股票数量
    actual_stocks = df.index.get_level_values("instrument").unique()

    print(f"  加载完成: {len(df)} 条记录")
    print(f"  实际股票数: {len(actual_stocks)} 只")
    print(f"  特征数: {len(feature_names)}")
    print(
        f"  日期范围: {df.index.get_level_values('datetime').min()} ~ {df.index.get_level_values('datetime').max()}"
    )

    return df, feature_names


def prepare_train_valid_test(df, feature_names, train_end, valid_end):
    """
    划分训练集、验证集、测试集

    Args:
        df: 完整数据集
        feature_names: 特征名列表
        train_end: 训练集结束日期
        valid_end: 验证集结束日期
    """
    print("\n[2/7] 划分数据集...")

    # 获取日期索引
    dates = df.index.get_level_values("datetime")

    # 划分
    train_mask = dates <= train_end
    valid_mask = (dates > train_end) & (dates <= valid_end)
    test_mask = dates > valid_end

    train_df = df[train_mask]
    valid_df = df[valid_mask]
    test_df = df[test_mask]

    # 提取特征和标签
    X_train = train_df[feature_names].values
    y_train = train_df["label"].values
    X_valid = valid_df[feature_names].values
    y_valid = valid_df["label"].values
    X_test = test_df[feature_names].values
    y_test = test_df["label"].values

    print(f"  训练集: {X_train.shape} ({train_mask.sum()} 条)")
    print(f"  验证集: {X_valid.shape} ({valid_mask.sum()} 条)")
    print(f"  测试集: {X_test.shape} ({test_mask.sum()} 条)")

    # 保存完整 DataFrame 用于生成 pred.pkl
    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_valid": X_valid,
        "y_valid": y_valid,
        "X_test": X_test,
        "y_test": y_test,
        "train_df": train_df,
        "valid_df": valid_df,
        "test_df": test_df,
        "feature_names": feature_names,
    }


def train_lightgbm_model(dataset):
    """训练 LightGBM 模型"""
    print("\n[3/7] 训练 LightGBM 模型...")

    model = LGBMRegressor(
        objective="regression",
        num_leaves=31,
        learning_rate=0.05,
        n_estimators=200,
        max_depth=7,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    model.fit(
        dataset["X_train"],
        dataset["y_train"],
        eval_set=[(dataset["X_valid"], dataset["y_valid"])],
        eval_metric="l2",
        callbacks=[],  # 禁用 early_stopping
    )

    print("  [OK] 模型训练完成")
    return model


def evaluate_model(model, dataset):
    """评估模型性能"""
    print("\n[4/7] 评估模型性能...")

    # 训练集
    train_pred = model.predict(dataset["X_train"])
    train_ic = calculate_ic(train_pred, dataset["y_train"])

    # 验证集
    valid_pred = model.predict(dataset["X_valid"])
    valid_ic = calculate_ic(valid_pred, dataset["y_valid"])

    # 测试集
    test_pred = model.predict(dataset["X_test"])
    test_mse = mean_squared_error(dataset["y_test"], test_pred)
    test_mae = mean_absolute_error(dataset["y_test"], test_pred)
    test_r2 = r2_score(dataset["y_test"], test_pred)
    test_ic = calculate_ic(test_pred, dataset["y_test"])

    print(f"\n  训练集 IC:  {train_ic:.4f}")
    print(f"  验证集 IC:  {valid_ic:.4f}")
    print(f"  测试集 IC:  {test_ic:.4f}")
    print(f"  测试集 MSE: {test_mse:.6f}")
    print(f"  测试集 MAE: {test_mae:.6f}")
    print(f"  测试集 R2:  {test_r2:.4f}")

    return {
        "train_ic": train_ic,
        "valid_ic": valid_ic,
        "test_ic": test_ic,
        "test_mse": test_mse,
        "test_mae": test_mae,
        "test_r2": test_r2,
    }


def normalize_scores(pred_df: pd.DataFrame) -> pd.DataFrame:
    """按日期正则化 score 使每一天的信号幅度可控"""

    def normalize(group: pd.Series) -> pd.Series:
        mean = group.mean()
        std = group.std(ddof=0)
        values = group - mean
        if std > 1e-9:
            values = values / std
        return values.clip(-0.05, 0.05)

    normalized = pred_df.copy()
    normalized["score"] = (
        normalized["score"].groupby(level="datetime").transform(normalize)
    )
    return normalized


def generate_predictions(model, dataset):
    """为整个时间段生成预测"""
    print("\n[5/7] 生成完整预测...")

    # 合并所有数据
    all_df = pd.concat(
        [
            dataset["train_df"],
            dataset["valid_df"],
            dataset["test_df"],
        ]
    )

    # 预测
    X_all = all_df[dataset["feature_names"]].values
    predictions = model.predict(X_all)

    # 创建 pred.pkl 格式的 DataFrame
    pred_df = pd.DataFrame({"score": predictions}, index=all_df.index)

    print(f"  预测数量: {len(pred_df)}")
    print(
        f"  日期范围: {pred_df.index.get_level_values('datetime').min()} ~ {pred_df.index.get_level_values('datetime').max()}"
    )
<<<<<<< HEAD
    print(f"  股票数量: {len(pred_df.index.get_level_values('instrument').unique())}")
=======
    print(
        f"  股票数量: {len(pred_df.index.get_level_values('instrument').unique())}")
>>>>>>> refactor/service-cleanup

    pred_df = normalize_scores(pred_df)
    stats = pred_df["score"].describe()
    print("  归一化后得分统计:")
    print(
        f"    min={stats['min']:.6f} 25%={stats['25%']:.6f} "
        f"median={stats['50%']:.6f} 75%={stats['75%']:.6f} max={stats['max']:.6f}"
    )
    print(f"    mean={stats['mean']:.6f} std={stats['std']:.6f}")
    return pred_df


def save_model_and_predictions(model, pred_df, metrics, feature_names, output_dir):
    """保存模型和预测结果"""
    print("\n[6/7] 保存模型和结果...")

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = Path(output_dir) / f"lightgbm_csi300_{timestamp}"
    model_dir.mkdir(parents=True, exist_ok=True)

    # 保存模型
    model_path = model_dir / "model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  [OK] 模型: {model_path}")

    # 保存元数据
    metadata = {
        "model_type": "LightGBM",
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
    print(f"  [OK] 元数据: {metadata_path}")

    # 保存 pred.pkl
    pred_path = model_dir / "pred.pkl"
    with open(pred_path, "wb") as f:
        pickle.dump(pred_df, f)
    print(f"  [OK] 预测结果: {pred_path}")

    # 特征重要性
    feature_importance = pd.DataFrame(
        {"feature": feature_names, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    importance_path = model_dir / "feature_importance.csv"
    feature_importance.to_csv(importance_path, index=False)
    print(f"  [OK] 特征重要性: {importance_path}")

    return model_dir, pred_path


def main():
    """主流程"""
    print("=" * 80)
    print("LightGBM 完整数据集训练流程")
    print("=" * 80)

    # 配置参数
    QLIB_DATA_PATH = "E:/code/quantmind/research/data_adapter/qlib_data"
    OUTPUT_DIR = "../../models/candidates"

    # 时间划分
    START_DATE = "2020-01-01"
    TRAIN_END = "2023-06-30"  # 训练集：2020-2023.6
    VALID_END = "2023-12-31"  # 验证集：2023.7-2023.12
    END_DATE = "2024-12-31"  # 测试集：2024全年

    UNIVERSE = "csi300"

    # 初始化 Qlib
    print("\n[0/7] 初始化 Qlib...")
    qlib.init(provider_uri=QLIB_DATA_PATH, region="cn")
    C["joblib_backend"] = "threading"
    C["kernels"] = 1
    print(f"  [OK] Qlib 数据路径: {QLIB_DATA_PATH}")

    # 加载数据
    df, feature_names = load_qlib_data(
        START_DATE, END_DATE, instruments=None, universe=UNIVERSE
    )

    # 划分数据集
    dataset = prepare_train_valid_test(df, feature_names, TRAIN_END, VALID_END)

    # 训练模型
    model = train_lightgbm_model(dataset)

    # 评估性能
    metrics = evaluate_model(model, dataset)

    # 生成预测
    pred_df = generate_predictions(model, dataset)

    # 保存
    model_dir, pred_path = save_model_and_predictions(
        model, pred_df, metrics, feature_names, OUTPUT_DIR
    )

    print("\n[7/7] 复制 pred.pkl 到工作目录...")
    import shutil

    # 复制到 predictions 目录（Qlib Service 默认读取位置）
    target_pred_dir = Path(
        "E:/code/quantmind/research/data_adapter/qlib_data/predictions"
    )
    target_pred_dir.mkdir(parents=True, exist_ok=True)
    target_pred_path = target_pred_dir / "pred.pkl"
    shutil.copy(pred_path, target_pred_path)
    print(f"  [OK] 已复制到: {target_pred_path}")

    # 同时复制到 data_adapter 目录（保持兼容）
    compat_pred_path = Path("E:/code/quantmind/research/data_adapter/pred.pkl")
    shutil.copy(pred_path, compat_pred_path)
    print(f"  [OK] 已复制到: {compat_pred_path} (兼容)")

    # 完成
    print("\n" + "=" * 80)
    print("[OK] 训练完成！")
    print("=" * 80)
    print(f"\n模型目录: {model_dir}")
    print(f"测试集 IC: {metrics['test_ic']:.4f}")
    print(f"预测数量: {len(pred_df)}")
    print("\n下一步:")
    print("  1. 重启 Qlib Service")
    print("  2. 在前端运行回测")
    print("  3. 验证策略收益不再为 0")
    print("=" * 80)


if __name__ == "__main__":
    main()
