下面是已经**完整整合你所有要求后的最终版本文档**（已统一硬件、环境、参数说明、流程规范），可以直接作为团队标准使用。

---

# LightGBM 模型训练方案（最终整合版）

---

## 1. 文档目标

本文档用于规范基于 **Qlib + LightGBM** 的量化模型训练流程，覆盖：

* 环境准备
* 数据导入
* 训练计划制定
* 特征处理
* Qlib 数据转换
* 模型训练
* 模型评估（IC）
* 历史预测生成
* 回测验证

适用于：

* A 股截面选股模型
* 日频 / 中低频预测
* LightGBM 回归或排序模型

---

## 2. 整体流程概览

完整流程如下：

1. AutoDL 环境准备
2. 克隆 Qlib 并安装依赖
3. 数据导入（DuckDB）
4. 制定训练计划
5. 特征提取 + Qlib 转换
6. 模型训练
7. 模型评估（IC 分析）
8. 生成预测文件
9. 回测验证

---

## 3. 环境准备

### 3.1 AutoDL 账号

* 注册 AutoDL
* 充值 ≥10 元
* 选择：**北京 B 区**

---

### 3.2 推荐硬件配置（强制标准）

为保证训练稳定性，统一要求：

* **CPU：16 核及以上**
* **内存：60GB 及以上**
* **磁盘：50GB 以上**

说明：

* 16 核 → 支撑 LightGBM 多线程训练
* 60GB 内存 → 支撑全市场 + 多年数据 + 特征计算
* 磁盘 → 存储数据、模型、日志

---

### 3.3 Python 与依赖版本统一（强制约束）

为保证训练与回测完全一致，统一：

* **Python：3.10**
* **NumPy：1.26.4**

适用范围：

* 数据处理
* 特征计算
* 模型训练
* 模型加载
* 回测

#### 原因：

1）避免依赖不兼容
2）避免 pkl 模型加载失败
3）避免数值计算差异

---

### 3.4 环境创建

```bash
conda create -n qlib_py310 python=3.10 -y
conda activate qlib_py310
```

---

### 3.5 项目目录结构

```bash
/workspace/lgbm_qlib_project/
├── qlib/
├── raw_data/
├── db/
├── scripts/
├── configs/
├── models/
├── preds/
├── logs/
└── backtest/
```

---

## 4. Qlib 安装

```bash
git clone https://github.com/microsoft/qlib
cd qlib
```

安装依赖（统一版本）：

```bash
pip install numpy==1.26.4
pip install lightgbm duckdb pandas pyarrow pyyaml matplotlib scikit-learn scipy joblib ruamel.yaml
pip install -r requirements.txt
pip install -e .
```

验证：

```bash
python -c "import qlib"
```

---

## 5. 数据导入（DuckDB）

### 5.1 推荐数据字段

必须包含：

* instrument
* datetime
* open / high / low / close
* volume / amount
* adj_factor（复权因子）
* 特征字段
* label（收益）

---

### 5.2 导入示例

```python
import duckdb
import pandas as pd

df = pd.read_csv('data.csv')
con = duckdb.connect('market.duckdb')
con.execute('CREATE TABLE stock_data AS SELECT * FROM df')
```

---

## 6. 训练计划制定

### 6.1 标签选择

推荐：

* **T+3（首选）**
* T+1（高频）

---

### 6.2 数据划分（强制规范）

* 训练集：2 年
* 验证集：6 个月
* 测试集：6 个月

---

### 6.3 特征维度

推荐：

* **40 ~ 60 个特征**

分类：

* 动量
* 波动率
* 成交量
* 资金流
* 风格因子
* 行业
* 微观结构

---

### 6.4 复权方式（强制）

* **统一使用：后复权**

---

## 7. 数据处理与 Qlib 转换

### 7.1 SQL 提取

```sql
SELECT * FROM stock_data
```

---

### 7.2 数据清洗

必须执行：

* 去停牌
* 去 ST
* 缺失值处理
* 极值处理
* 时间对齐
* 防未来函数

---

### 7.3 转换 Qlib 数据

```bash
python convert_to_qlib.py
```

---

### 7.4 YAML 配置

```yaml
qlib_init:
  provider_uri: ./qlib_data
  region: cn
```

---

## 8. LightGBM 训练参数说明（核心）

以下为标准参数模板（推荐默认使用）：

```yaml
objective: regression
metric: l2
boosting_type: gbdt

learning_rate: 0.02
num_boost_round: 3500
early_stopping_rounds: 180

num_leaves: 95
max_depth: 11
min_data_in_leaf: 700

feature_fraction: 0.8
bagging_fraction: 0.9
bagging_freq: 1

lambda_l1: 1.0
lambda_l2: 5.0

max_bin: 255
min_gain_to_split: 0.0

force_col_wise: true
num_threads: 16
```

---

### 8.1 核心设计思想

#### （1）防过拟合

* min_data_in_leaf = 700
* lambda_l2 = 5
* 双随机采样

---

#### （2）慢学习

* learning_rate = 0.02
* 大轮数训练

---

#### （3）稳定优先

该配置不是追求训练集最优，而是：

👉 **验证集稳定 + 测试集可泛化**

---

## 9. 模型训练

```bash
python train_lgbm.py \
  --config configs/lgbm.yaml \
  --model_output models/lgbm.bin
```

---

## 10. 模型评估（重点）

### 核心指标：

* IC
* RankIC
* ICIR
* TopK 收益

---

### 必须检查：

#### 1）IC 是否为正

#### 2）IC 是否稳定

#### 3）是否出现衰减

---

### 异常情况处理

如果出现：

* IC 低
* IC 衰减

需要：

* 降低模型复杂度
* 调整特征
* 增加正则
* 清洗数据

---

## 11. 生成预测文件

输出格式：

* **pkl**

字段：

* datetime
* instrument
* score

---

```bash
python generate_pred.py \
  --model models/lgbm.bin \
  --output preds/pred.pkl
```

---

## 12. 回测验证

### 检查指标：

* 年化收益
* Sharpe
* 最大回撤
* 多空收益
* 换手率

---

### 核心验证点：

#### 1）收益是否稳定

#### 2）回撤是否可控

#### 3）换手是否过高

#### 4）多空是否同时有效

---

## 13. 首版标准（统一执行）

### 数据：

* A 股
* 日频
* 后复权

---

### 标签：

* **T+3**

---

### 特征：

* **40~60**

---

### 数据切分：

* 2Y / 6M / 6M

---

### 硬件：

* **16 核 CPU**
* **60GB 内存**

---

### 环境（强制）：

* **Python 3.10**
* **NumPy 1.26.4**

---

## 14. 风险与注意事项

### 14.1 数据泄漏（最高优先级）

* 标签错位
* 使用未来数据

---

### 14.2 过拟合

* 特征过多
* 树过深

---

### 14.3 环境不一致（高风险）

可能导致：

* 模型加载失败
* 回测结果偏差

👉 必须统一 Python 和 NumPy

---

### 14.4 训练 vs 回测不一致

必须保证：

* 股票池一致
* 复权一致
* 特征一致

---

## 15. 结论

本方案核心原则：

👉 **稳定优先，而不是极致拟合**

统一标准：

* 环境统一
* 数据统一
* 参数统一
* 流程统一

先跑通闭环，再优化：

* 特征
* 参数
* 策略


