# QuantMind - 智能量化交易平台 (OSS 开源版)

> 🚀 基于微服务架构的高性能量化交易系统。**开源版 (OSS)** 支持本地一键部署，零云服务依赖。

---

## 🏗️ 架构概览

QuantMind OSS 版采用**单镜像部署**，所有后端服务运行在一个容器内：

```
┌─────────────────────────────────────────────────────────┐
│                    QuantMind 容器                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │   API   │ │ Engine  │  │  Trade  │ │ Stream  │       │
│  │ :8000   │ │ :8001   │  │ :8002   │ │ :8003   │       │
│  └─────────┘ └─────────┘  └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────┘
         │              │              │
    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
    │PostgreSQL│    │  Redis  │    │ 本地存储 │
    │  :5432  │    │  :6379  │    │  /data  │
    └─────────┘    └─────────┘    └─────────┘
```

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API Gateway | 8000 | 用户认证、策略管理、社区等 |
| Engine | 8001 | Qlib 回测引擎、AI 策略生成 |
| Trade | 8002 | 订单管理、持仓、风控 |
| Stream | 8003 | 实时行情、WebSocket 推送 |

### Redis 数据库分配

| DB | 用途 |
|----|------|
| 0 | 默认/通用 |
| 1 | 认证相关 |
| 2 | 交易服务 |
| 3 | 行情数据 |
| 4 | 回测引擎 |
| 5 | 缓存 |

---

## 🚀 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- Node.js 18+ (前端开发)
- 8GB+ 内存

### 1. 启动后端服务

```bash
# 克隆项目
git clone https://github.com/your-repo/quantmind.git
cd quantmind

# 启动所有服务（PostgreSQL + Redis + QuantMind）
docker-compose up -d

# 查看日志
docker-compose logs -f quantmind
```

服务启动后：
- API 地址: `http://localhost:8000`
- 健康检查: `http://localhost:8000/health`

### 2. 下载模型和数据 (可选)

AI 推理和回测功能需要模型和历史数据：

```bash
# 下载 AI 模型 (约 400MB)
# 将模型文件放入 models/production/ 目录

# 下载 Qlib 历史数据 (约 800MB)
# 将数据文件放入 db/qlib_data/ 目录
```

> **说明**: 不下载模型和数据不影响基础功能，但 AI 策略生成和回测预测功能将不可用。

### 3. 启动前端应用

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产包
npm run dashboard:build
cd electron && npm run build:package
```

### 3. 访问应用

- 开发模式: `http://localhost:3000`
- 桌面应用: 打包后运行 `dist/` 目录下的安装包

---

## ⚙️ 配置说明

### 环境变量

主要配置通过 `.env` 文件管理：

```bash
# 数据库
DB_HOST=db
DB_PORT=5432
DB_NAME=quantmind
DB_USER=quantmind
DB_PASSWORD=your-password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# 安全
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-key

# 存储 (本地)
STORAGE_MODE=local
STORAGE_ROOT=/data
```

### 单服务模式

如需单独运行某个服务：

```bash
# 仅运行 API
docker run -e SERVICE_MODE=api -p 8000:8000 quantmind-oss

# 仅运行 Engine
docker run -e SERVICE_MODE=engine -p 8001:8001 quantmind-oss
```

---

## 🧪 开发与测试

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 运行单元测试
python backend/run_tests.py unit

# 环境健康检查
python scripts/health_check.py
```

---

## 📁 目录结构

```
quant/
├── backend/
│   ├── main_oss.py          # OSS 统一入口
│   ├── services/
│   │   ├── api/             # API 服务 (8000)
│   │   ├── engine/          # 回测引擎 (8001)
│   │   ├── trade/           # 交易服务 (8002)
│   │   └── stream/          # 行情服务 (8003)
│   └── shared/              # 共享模块
├── electron/                # 前端应用
├── docker/
│   └── Dockerfile.oss       # OSS 镜像构建
├── docker-compose.yml       # 部署配置
└── requirements.txt         # Python 依赖
```

---

## 📄 License

MIT License
