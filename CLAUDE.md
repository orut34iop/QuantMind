# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuantMind is a quantitative trading platform with Python backend (FastAPI) and Electron/React/TypeScript frontend. The OSS edition uses single-container deployment where all backend services run in one container.

## Backend Services (all via `backend/main_oss.py`)

| Service | Port | Responsibility |
|---------|------|----------------|
| api | 8000 | User auth, strategy management, community |
| engine | 8001 | Qlib backtesting, AI strategy generation, model inference |
| trade | 8002 | Order management, positions, risk control |
| stream | 8003 | Real-time quotes, WebSocket push |

The `api` service acts as the gateway and proxies routes to other services:
- Proxy to `engine`: `/api/v1/strategies*`, `/api/v1/qlib/*`, `/api/v1/analysis*`, `/api/v1/inference/*`, `/api/v1/pipeline/*`, `/api/v1/stocks/*`, `/api/v1/selection*`, `/api/v1/strategy-backtest-loop/*`
- Proxy to `trade`: `/api/v1/orders/*`, `/api/v1/trades/*`, `/api/v1/portfolios/*`, `/api/v1/simulation/*`, `/api/v1/real-trading/*`, `/api/v1/internal/strategy/*`

## Commands

### Backend
```bash
# Start all services (Docker)
docker-compose up -d

# Run single service locally
SERVICE_MODE=api python backend/main_oss.py
SERVICE_MODE=engine python backend/main_oss.py
SERVICE_MODE=trade python backend/main_oss.py
SERVICE_MODE=stream python backend/main_oss.py

# Tests (run from project root)
python backend/run_tests.py unit        # Unit tests
python backend/run_tests.py integration # Integration tests
python backend/run_tests.py all         # All tests
python backend/run_tests.py trade-long-short  # QMT MVP chain tests

# Run a single test file directly
pytest -q backend/services/tests/test_trade_service.py
pytest -q backend/services/tests/test_api_service.py
pytest -q backend/services/tests/test_stream_service.py

# Lint/format
ruff check backend/
ruff format backend/

# Schema registry audit
python backend/scripts/schema_registry_audit.py
python backend/scripts/schema_registry_audit.py --check-db

# Celery worker (for async backtests and auto-inference)
celery -A backend.services.engine.qlib_app.celery_config:celery_app \
  worker -Q qlib_backtest --loglevel=info --concurrency=2
```

### Frontend (Electron app in `electron/`)
```bash
npm install              # Install dependencies
npm run dev              # Development (Electron desktop)
npm run dev:react        # Development (Vite dev server on :3000)
npm run typecheck        # Type check
npm run lint             # ESLint
npm run dashboard:build  # Production build
npm test                 # Unit tests (vitest)
npm run test:e2e         # End-to-end tests (playwright)
```

## Architecture Notes

- **Feature engineering**: 48-dim features written to `market_data_daily` table by external service
- **Trade service**: Enforces "local-first" order persistence before external submission
- **Redis DB allocation**: 0=general, 1=auth, 2=trade, 3=market, 4=backtest, 5=cache
- **Shared modules**: `backend/shared/` contains cross-service code (DB manager, Redis client, config, logging)
- **Strategy storage**: `backend/shared/strategy_storage.py` is the single entry point for all strategy CRUD operations
- **Model registry**: `backend/shared/model_registry.py` handles user model registration, default model resolution, and strategy-to-model bindings
- **Trading calendar**: `backend/shared/trading_calendar.py` provides unified trading day/session logic across services; resolves user-level overrides first, then tenant-level, then global defaults
- **Async tasks**: `engine` uses Celery for backtests, optimization, and auto-inference. The `celery-worker` container runs the worker; `celery-beat` is required for the 08:55 auto-inference schedule
- **Training orchestration**: `LocalDockerOrchestrator` spins up training containers locally; `BatchOrchestrator` submits to Tencent BatchCompute. Both use `quantmind-ml-runtime:latest`
- **Live execution pipeline**: Runner consumes Redis Stream (`qm:signal:stream:{tenant}`), applies risk controls, then submits orders via internal gateway (`/api/v1/internal/strategy/order`) to the trade service. QMT Agent is the supported broker integration
- **Data directories**:
  - `db/qlib_data/` — Qlib backtest data (calendars, instruments, features)
  - `db/feature_snapshots/` — Model training data (Parquet format)
  - `models/production/` — System models (alpha158, model_qlib)
  - `models/users/{tenant_id}/{user_id}/{model_id}/` — User-trained models
  - `data/backtest_results/` — Backtest result outputs
  - `data/stocks/stocks_index.json` — Local stock search index

## Docker Compose Services

The `docker-compose.yml` defines:
- `db` — PostgreSQL 15
- `redis` — Redis 7 (16 databases, AOF enabled)
- `quantmind` — Core backend services (all 4 services in one container when `SERVICE_MODE=all`)
- `celery-worker` — Async task worker for engine backtests

## Environment

Required `.env` keys (defaults in `docker-compose.yml`):
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`
- `SECRET_KEY`, `JWT_SECRET_KEY`
- `STORAGE_MODE=local` for OSS edition

## Code Style

- Python: Line length 88, use ruff for linting/formatting (configured in `pyproject.toml`)
- TypeScript: Run `npm run typecheck` before committing frontend changes

## Deployment Workflow

After making code changes, always:
1. **Commit to git**: Create a commit with descriptive message
2. **Deploy to server**: SSH to `quant-server` and pull/deploy updates

```bash
# Local: commit changes
git add .
git commit -m "descriptive message"

# Deploy to quant-server
ssh quant-server "cd /opt/quantmind/quantmind && git pull && docker-compose restart"
```

## Key Files

- `backend/main_oss.py` — Unified entry point for all backend services
- `backend/run_tests.py` — Test runner with multiple modes
- `backend/shared/` — Shared modules across services
- `docker-compose.yml` — Local deployment configuration
