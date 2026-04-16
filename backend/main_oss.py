"""
QuantMind OSS Edition - Unified Service Entry Point
单镜像运行所有后端服务

服务端口分配:
- API Gateway: 8000 (主入口)
- Engine: 8001 (回测引擎)
- Trade: 8002 (交易服务)
- Stream: 8003 (实时行情)
"""

import asyncio
import logging
import multiprocessing as mp
import os
import sys
from typing import Optional

try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass

from backend.shared.logging_config import setup_logging

setup_logging(service_name="quantmind-oss")
logger = logging.getLogger(__name__)


def get_service_ports() -> dict:
    """获取服务端口配置"""
    return {
        "api": int(os.getenv("API_PORT", "8000")),
        "engine": int(os.getenv("ENGINE_PORT", "8001")),
        "trade": int(os.getenv("TRADE_PORT", "8002")),
        "stream": int(os.getenv("STREAM_PORT", "8003")),
    }


def run_api_service(port: int):
    """运行 API 服务"""
    import uvicorn
    from backend.services.api.main import app

    logger.info(f"Starting API service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)


def run_engine_service(port: int):
    """运行 Engine 服务"""
    import uvicorn
    from backend.services.engine.main import app

    logger.info(f"Starting Engine service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)


def run_trade_service(port: int):
    """运行 Trade 服务"""
    import uvicorn
    from backend.services.trade.main import app

    logger.info(f"Starting Trade service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)


def run_stream_service(port: int):
    """运行 Stream 服务"""
    import uvicorn
    from backend.services.stream.main import app

    logger.info(f"Starting Stream service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, access_log=False)


def run_single_service(service_name: str, port: int):
    """运行单个服务（用于调试或按需启动）"""
    service_runners = {
        "api": run_api_service,
        "engine": run_engine_service,
        "trade": run_trade_service,
        "stream": run_stream_service,
    }

    if service_name not in service_runners:
        raise ValueError(
            f"Unknown service: {service_name}. Available: {list(service_runners.keys())}"
        )

    service_runners[service_name](port)


def run_all_services():
    """运行所有服务（多进程模式）"""
    ports = get_service_ports()

    services = [
        ("api", run_api_service, ports["api"]),
        ("engine", run_engine_service, ports["engine"]),
        ("trade", run_trade_service, ports["trade"]),
        ("stream", run_stream_service, ports["stream"]),
    ]

    processes = []

    for name, runner, port in services:
        p = mp.Process(target=runner, args=(port,), name=f"quantmind-{name}")
        p.start()
        processes.append((name, p))
        logger.info(f"Started {name} service (PID: {p.pid}) on port {port}")

    logger.info("=" * 60)
    logger.info("QuantMind OSS Edition - All services started")
    logger.info(f"  API Gateway:  http://localhost:{ports['api']}")
    logger.info(f"  Engine:       http://localhost:{ports['engine']}")
    logger.info(f"  Trade:        http://localhost:{ports['trade']}")
    logger.info(f"  Stream:       http://localhost:{ports['stream']}")
    logger.info("=" * 60)

    try:
        for name, p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down all services...")
        for name, p in processes:
            if p.is_alive():
                p.terminate()
                logger.info(f"Terminated {name} service")

        for name, p in processes:
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
                logger.warning(f"Force killed {name} service")


def main():
    """主入口"""
    service_mode = os.getenv("SERVICE_MODE", "all").lower().strip()
    ports = get_service_ports()

    logger.info(f"QuantMind OSS Edition - Service Mode: {service_mode}")

    if service_mode == "all":
        run_all_services()
    elif service_mode in ("api", "engine", "trade", "stream"):
        run_single_service(service_mode, ports[service_mode])
    else:
        logger.error(f"Unknown SERVICE_MODE: {service_mode}")
        logger.info("Valid modes: all, api, engine, trade, stream")
        sys.exit(1)


if __name__ == "__main__":
    main()
