#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AkShare 行情快照写入 Redis

职责：
- 拉取 A 股全市场最新行情快照
- 按 `stock:{code}.{market}` 写入远程 Redis
- 维护 1 小时过期时间，供 `quantmind-stream` 读取

说明：
- 这是一个可独立部署的常驻任务
- `quantmind-stream` 只消费 `stock:*` 快照，不负责采集
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import akshare as ak
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: akshare. Install with `pip install -r requirements/data.txt`."
    ) from exc

try:
    import redis
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: redis. Install with `pip install -r requirements/data.txt`."
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[2]
ROOT_ENV = ROOT_DIR / ".env"
logger = logging.getLogger("market_data_to_redis")


def _load_root_env() -> None:
    """轻量级 .env 加载器，仅补齐未设置的变量。"""
    if not ROOT_ENV.exists():
        return

    try:
        for line in ROOT_ENV.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            if not key or os.getenv(key) is not None:
                continue
            os.environ[key] = value.strip().strip("'").strip('"')
    except Exception as exc:
        logger.warning("Failed to load root .env: %s", exc)


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _normalize_symbol(code: Any) -> Optional[str]:
    """将 AkShare / 内部股票代码统一成 `600000.SH` 这类格式。"""
    s = str(code or "").strip().upper()
    if not s:
        return None
    if "." in s:
        return s
    if s.startswith("SH"):
        return f"{s[2:]}.SH"
    if s.startswith("SZ"):
        return f"{s[2:]}.SZ"
    if s.startswith("BJ"):
        return f"{s[2:]}.BJ"
    if s.startswith("6"):
        return f"{s}.SH"
    if s.startswith(("0", "2", "3")):
        return f"{s}.SZ"
    if s.startswith(("4", "8", "9")):
        return f"{s}.BJ"
    return f"{s}.SH"


def _first_present(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


@dataclass
class SnapshotResult:
    total: int
    written: int
    skipped: int


class MarketDataToRedis:
    """将 AkShare 实时行情快照写入 Redis。"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        db: Optional[int] = None,
        expire_seconds: Optional[int] = None,
        retry_count: Optional[int] = None,
        retry_delay_seconds: Optional[float] = None,
    ) -> None:
        _load_root_env()

        self.host = (host or _env("REDIS_MARKET_HOST", "REMOTE_QUOTE_REDIS_HOST", default="localhost")).strip()
        self.port = int(port if port is not None else _env("REDIS_MARKET_PORT", "REMOTE_QUOTE_REDIS_PORT", default="36379"))
        self.password = (password if password is not None else _env("REDIS_MARKET_PASSWORD", "REMOTE_QUOTE_REDIS_PASSWORD", default="")).strip() or None
        self.db = int(db if db is not None else _env("REDIS_MARKET_DB", "REDIS_DB_MARKET", default="0"))
        self.expire_seconds = int(
            expire_seconds if expire_seconds is not None else _env("MARKET_DATA_EXPIRE_SECONDS", default="3600")
        )
        self.retry_count = int(retry_count if retry_count is not None else _env("MARKET_DATA_RETRY_COUNT", default="3"))
        self.retry_delay_seconds = float(
            retry_delay_seconds if retry_delay_seconds is not None else _env("MARKET_DATA_RETRY_DELAY_SECONDS", default="2")
        )
        self.batch_size = int(_env("MARKET_DATA_BATCH_SIZE", default="80"))
        self.interval_seconds = int(_env("MARKET_DATA_INTERVAL_SECONDS", default="60"))
        self.source_name = _env("MARKET_DATA_SOURCE", default="akshare")
        self.market_filter = _env("MARKET_DATA_MARKET_FILTER", default="A").upper()

        self.redis = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            db=self.db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        self._stop_requested = False

    def _log_config(self) -> None:
        logger.info(
            "Redis target: %s:%s db=%s expire=%ss batch_size=%s interval=%ss source=%s",
            self.host,
            self.port,
            self.db,
            self.expire_seconds,
            self.batch_size,
            self.interval_seconds,
            self.source_name,
        )

    def _select_snapshot_df(self):
        """拉取最新行情快照，失败则重试。"""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_count + 1):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is None or getattr(df, "empty", True):
                    raise RuntimeError("empty snapshot dataframe")
                return df
            except Exception as exc:  # pragma: no cover
                last_error = exc
                logger.warning("Fetch snapshot failed (attempt %s/%s): %s", attempt, self.retry_count, exc)
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay_seconds)
        raise RuntimeError(f"Failed to fetch market snapshot: {last_error}")

    def _extract_rows(self, df) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        now_ts = int(time.time())

        for _, raw in df.iterrows():
            row = raw.to_dict()
            code = _first_present(row, "代码", "symbol", "code")
            symbol = _normalize_symbol(code)
            if not symbol:
                continue

            current_price = _to_float(_first_present(row, "最新价", "price", "current_price"))
            if current_price is None:
                continue

            open_price = _to_float(_first_present(row, "今开", "open"))
            high_price = _to_float(_first_present(row, "最高", "high"))
            low_price = _to_float(_first_present(row, "最低", "low"))
            close_price = _to_float(_first_present(row, "昨收", "pre_close", "close"), default=current_price)
            volume = _to_int(_first_present(row, "成交量", "volume"), default=0)
            amount = _to_float(_first_present(row, "成交额", "amount"))

            rows.append(
                {
                    "key": f"stock:{symbol}",
                    "symbol": symbol,
                    "mapping": {
                        "Now": current_price,
                        "Open": open_price if open_price is not None else current_price,
                        "High": high_price,
                        "Low": low_price,
                        "Close": close_price,
                        "Volume": volume,
                        "Amount": amount if amount is not None else 0.0,
                        "timestamp": now_ts,
                    },
                }
            )

        return rows

    def _write_batch(self, items: Iterable[Dict[str, Any]]) -> int:
        written = 0
        pipe = self.redis.pipeline(transaction=False)
        for item in items:
            pipe.hset(item["key"], mapping=item["mapping"])
            pipe.expire(item["key"], self.expire_seconds)
            written += 1
        pipe.execute()
        return written

    def get_market_snapshot(self, batch_size: Optional[int] = None) -> int:
        """拉取一次市场快照并写入 Redis。"""
        df = self._select_snapshot_df()
        rows = self._extract_rows(df)
        if not rows:
            logger.warning("No market rows extracted from snapshot")
            return 0

        effective_batch_size = int(batch_size or self.batch_size or 80)
        total_written = 0
        for start in range(0, len(rows), effective_batch_size):
            chunk = rows[start : start + effective_batch_size]
            total_written += self._write_batch(chunk)

        logger.info("Snapshot written: total=%s written=%s", len(rows), total_written)
        return total_written

    def get_stock_data(self, symbol: str) -> Dict[str, Any]:
        key = f"stock:{_normalize_symbol(symbol) or symbol}"
        return self.redis.hgetall(key)

    def clear_all_data(self) -> int:
        """清理当前 Redis 中所有 stock:* 快照。"""
        keys = list(self.redis.scan_iter("stock:*"))
        if not keys:
            return 0
        return int(self.redis.delete(*keys))

    def close(self) -> None:
        try:
            self.redis.close()
        except Exception:
            try:
                self.redis.connection_pool.disconnect()
            except Exception:
                pass

    def run_once(self, batch_size: Optional[int] = None) -> int:
        self._log_config()
        self.redis.ping()
        return self.get_market_snapshot(batch_size=batch_size)

    def stop(self) -> None:
        self._stop_requested = True

    def run_forever(self, interval_seconds: Optional[int] = None, batch_size: Optional[int] = None) -> None:
        """持续拉取市场快照，直到收到退出信号。"""
        interval = int(interval_seconds or self.interval_seconds or 60)
        self._log_config()
        logger.info("Starting market data loop with interval=%ss", interval)

        while not self._stop_requested:
            started_at = time.time()
            try:
                self.redis.ping()
                written = self.get_market_snapshot(batch_size=batch_size)
                logger.info("Snapshot loop completed: written=%s elapsed=%.2fs", written, time.time() - started_at)
            except Exception as exc:
                logger.exception("Snapshot loop failed: %s", exc)

            if self._stop_requested:
                break

            elapsed = time.time() - started_at
            sleep_seconds = max(1, interval - int(elapsed))
            for _ in range(sleep_seconds):
                if self._stop_requested:
                    break
                time.sleep(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write AkShare market snapshots into Redis.")
    parser.add_argument("--once", action="store_true", help="Run a single snapshot write and exit.")
    parser.add_argument("--interval", type=int, default=None, help="Loop interval seconds.")
    parser.add_argument("--batch-size", type=int, default=None, help="Redis write batch size.")
    parser.add_argument("--expire-seconds", type=int, default=None, help="Redis key TTL in seconds.")
    parser.add_argument("--host", type=str, default=None, help="Redis host.")
    parser.add_argument("--port", type=int, default=None, help="Redis port.")
    parser.add_argument("--password", type=str, default=None, help="Redis password.")
    parser.add_argument("--db", type=int, default=None, help="Redis database index.")
    parser.add_argument("--log-level", type=str, default=None, help="Logging level.")
    return parser


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.log_level or _env("MARKET_DATA_LOG_LEVEL", default="INFO"))
    task = MarketDataToRedis(
        host=args.host,
        port=args.port,
        password=args.password,
        db=args.db,
        expire_seconds=args.expire_seconds,
    )

    def _handle_signal(_signum, _frame):
        logger.info("Stop signal received")
        task.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        if args.once or _env("MARKET_DATA_ONCE", default="false").lower() in {"1", "true", "yes", "on"}:
            written = task.run_once(batch_size=args.batch_size)
            logger.info("One-shot snapshot done: written=%s", written)
        else:
            task.run_forever(interval_seconds=args.interval, batch_size=args.batch_size)
    finally:
        task.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
