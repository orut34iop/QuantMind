# Data Sources 模块

本目录是 QuantMind 平台的**数据采集与中台中心**，负责从外部供应商抓取原始金融数据。

## 核心职责
- **多源接入**: 整合 AkShare (免费源) 与 iFinD (同花顺收费源) 的 API 访问。
- **数据对齐**: 通过 `data_sync.py` 自动修补本地历史数据的缺失空洞。
- **质量审计**: 利用 `sanitizer.py` 执行入库前的异常值（NaN、离群值）清洗。

## 目录结构
- `akshare_api.py`: AkShare 行情接口实现。
- `ths_api.py`: 同花顺 iFinD 数据接口实现。
- `data_manager.py`: 统一数据存储与本地文件管理。
- `data_sync.py`: 自动化增量更新与空洞修补逻辑。

## 注意事项
- 本模块被 `backend/services/stream/` (实时行情) 及根目录下的多个数据补全脚本引用。
- 修改接口逻辑时需确保向后兼容性。
