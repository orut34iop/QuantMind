#!/bin/bash
# ====================================================================
# QuantMind 数据库同步脚本 - Baostock -> PostgreSQL
# 时间：每日凌晨 02:00 执行
# 功能：从 Baostock 拉取最新行情数据到数据库
# ====================================================================

# 1. 基础环境配置
PROJECT_DIR="/home/quantmind"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
LOG_DIR="${PROJECT_DIR}/logs/data_sync"
LOG_FILE="${LOG_DIR}/sync_db_$(date +\%Y\%m\%d).log"

# 加载 .env 环境变量
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    . "${PROJECT_DIR}/.env"
    set +a
fi

# 创建日志目录
mkdir -p "${LOG_DIR}"

echo "📅 [$(date)] 开始数据库同步任务 (Baostock -> PostgreSQL)..." >> "${LOG_FILE}"

cd "${PROJECT_DIR}" || exit

# --------------------------------------------------------------------
# 从 Baostock 同步行情数据到数据库
# --------------------------------------------------------------------
echo "🚀 正在从 Baostock 同步数据到 market_data_daily 表..." >> "${LOG_FILE}"
"${PYTHON_BIN}" scripts/data/ingestion/sync_market_data_daily_from_baostock.py --apply 2>&1 | tee -a "${LOG_FILE}"

echo "✅ [$(date)] 数据库同步任务完成。" >> "${LOG_FILE}"
echo "--------------------------------------------------------" >> "${LOG_FILE}"
