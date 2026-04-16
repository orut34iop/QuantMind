# Data Adapter (Postgres -> Qlib)

This folder contains scripts to export OHLCV data from Postgres and convert it
into Qlib bin format.

## 1) Export from Postgres to CSV

```bash
python research/data_adapter/export_klines_to_csv.py \
  --table klines \
  --interval 1d \
  --output-dir research/data_adapter/raw/1d
```

Environment variables (optional):
- `DB_MASTER_HOST`, `DB_MASTER_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `QLIB_KLINES_TABLE`, `QLIB_KLINES_INTERVAL`, `QLIB_START_DATE`, `QLIB_END_DATE`
- `QLIB_RAW_DIR`

## 2) Convert CSV to Qlib bin

```bash
python research/data_adapter/convert_csv_to_qlib_bin.py \
  --data-path research/data_adapter/raw/1d \
  --qlib-dir research/data_adapter/qlib_data \
  --freq day
```

Notes:
- Each CSV file should be named by symbol (e.g., `000001.SZ.csv`).
- CSV columns should include: date, open, high, low, close, volume, amount.
- `psycopg2` is required for Postgres connections via SQLAlchemy.

> **提示**: `train_full_lightgbm.py` 在初始化时会自动设置 `PYTHONIOENCODING=utf-8` 并将 Qlib 的 joblib backend 切换为 `threading`（`kernels=1`），以避免 Windows 下因权限/管道限制导致的多进程异常。
