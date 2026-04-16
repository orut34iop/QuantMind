#!/usr/bin/env python3
"""
配置管理模块
提供akshare数据源的配置选项和错误处理机制
"""

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class LogLevel(Enum):
    """日志级别枚举"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RetryStrategy(Enum):
    """重试策略枚举"""

    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


@dataclass
class DatabaseConfig:
    """数据库配置"""

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = ""
    database: str = "quantmind"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    default_ttl: int = 300  # 5分钟
    max_size: int = 1000
    cleanup_interval: int = 600  # 10分钟
    redis_url: str | None = "redis://:redis_hA33hB@139.199.75.121:6379/0"
    redis_db: int = 0
    redis_password: str | None = "redis_hA33hB"


@dataclass
class RetryConfig:
    """重试配置"""

    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


@dataclass
class RateLimitConfig:
    """限流配置"""

    enabled: bool = True
    requests_per_second: float = 10.0
    requests_per_minute: int = 200
    requests_per_hour: int = 1000
    burst_size: int = 20


@dataclass
class AkShareConfig:
    """AkShare配置"""

    timeout: int = 30
    max_workers: int = 4
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    user_agent: str = "QuantMind/1.0"
    proxy: str | None = None
    verify_ssl: bool = True


@dataclass
class SyncConfig:
    """同步配置"""

    enabled: bool = True
    max_workers: int = 4
    default_schedule: str = "every_1h"
    gap_detection_enabled: bool = True
    gap_check_interval: int = 3600
    auto_fill_gaps: bool = True
    db_url: str = (
        "postgresql+psycopg2://postgres:your_pg_password_here@localhost:5432/quantmind"
    )
    log_retention_days: int = 30


@dataclass
class LoggingConfig:
    """日志配置"""

    level: LogLevel = LogLevel.INFO
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str | None = "./logs/akshare.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True
    json_format: bool = False


@dataclass
class SecurityConfig:
    """安全配置"""

    api_key_encryption: bool = True
    data_encryption: bool = False
    access_token_ttl: int = 3600
    allowed_ips: list[str] = field(default_factory=list)
    rate_limit_by_ip: bool = True


@dataclass
class MonitoringConfig:
    """监控配置"""

    enabled: bool = True
    metrics_endpoint: str = "/metrics"
    health_check_endpoint: str = "/health"
    performance_tracking: bool = True
    error_tracking: bool = True
    alert_thresholds: dict[str, float] = field(
        default_factory=lambda: {
            "error_rate": 0.05,  # 5%
            "response_time": 5.0,  # 5秒
            "memory_usage": 0.8,  # 80%
            "cpu_usage": 0.8,  # 80%
        }
    )


@dataclass
class DataSourceConfig:
    """数据源总配置"""

    akshare: AkShareConfig = field(default_factory=AkShareConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # 环境配置
    environment: str = "development"
    debug: bool = False

    # 数据存储配置
    data_dir: str = "./data"
    export_dir: str = "./exports"
    temp_dir: str = "./temp"

    # 性能配置
    max_concurrent_requests: int = 10
    request_timeout: int = 30
    connection_pool_size: int = 20


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_file: str | None = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file or "./config/akshare_config.yaml"
        self.config = DataSourceConfig()
        self.logger = logging.getLogger(__name__)

        # 加载配置
        self._load_config()

        # 设置日志
        self._setup_logging()

    def _load_config(self):
        """加载配置文件"""
        try:
            # 首先尝试从环境变量加载
            self._load_from_env()

            # 然后尝试从配置文件加载
            if os.path.exists(self.config_file):
                self._load_from_file()
            else:
                self.logger.info(f"配置文件不存在: {self.config_file}，使用默认配置")
                # 创建默认配置文件
                self._create_default_config_file()

            # 验证配置
            self._validate_config()

        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            raise

    def _load_from_env(self):
        """从环境变量加载配置"""
        # 数据库配置
        if os.getenv("DB_HOST"):
            self.config.database.host = os.getenv("DB_HOST")
        if os.getenv("DB_PORT"):
            self.config.database.port = int(os.getenv("DB_PORT"))
        if os.getenv("DB_USERNAME"):
            self.config.database.username = os.getenv("DB_USERNAME")
        if os.getenv("DB_PASSWORD"):
            self.config.database.password = os.getenv("DB_PASSWORD")
        if os.getenv("DB_DATABASE"):
            self.config.database.database = os.getenv("DB_DATABASE")

        # 缓存配置
        if os.getenv("REDIS_URL"):
            self.config.cache.redis_url = os.getenv("REDIS_URL")
        if os.getenv("REDIS_PASSWORD"):
            self.config.cache.redis_password = os.getenv("REDIS_PASSWORD")

        # 环境配置
        if os.getenv("ENVIRONMENT"):
            self.config.environment = os.getenv("ENVIRONMENT")
        if os.getenv("DEBUG"):
            self.config.debug = os.getenv("DEBUG").lower() == "true"

        # 日志配置
        if os.getenv("LOG_LEVEL"):
            self.config.logging.level = LogLevel(os.getenv("LOG_LEVEL"))
        if os.getenv("LOG_FILE"):
            self.config.logging.file_path = os.getenv("LOG_FILE")

    def _load_from_file(self):
        """从配置文件加载配置"""
        try:
            with open(self.config_file, encoding="utf-8") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(
                    ".yml"
                ):
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)

            # 递归更新配置
            self._update_config_from_dict(self.config, config_data)

            self.logger.info(f"从配置文件加载配置成功: {self.config_file}")

        except Exception as e:
            self.logger.error(f"从配置文件加载配置失败: {e}")
            raise

    def _update_config_from_dict(self, config_obj: Any, config_dict: dict[str, Any]):
        """从字典递归更新配置对象"""
        for key, value in config_dict.items():
            if hasattr(config_obj, key):
                attr = getattr(config_obj, key)
                if hasattr(attr, "__dict__"):  # 嵌套配置对象
                    if isinstance(value, dict):
                        self._update_config_from_dict(attr, value)
                else:
                    # 处理枚举类型
                    if hasattr(attr, "__class__") and issubclass(attr.__class__, Enum):
                        if isinstance(value, str):
                            setattr(config_obj, key, attr.__class__(value))
                    else:
                        setattr(config_obj, key, value)

    def _create_default_config_file(self):
        """创建默认配置文件"""
        try:
            # 创建配置目录
            config_dir = Path(self.config_file).parent
            config_dir.mkdir(parents=True, exist_ok=True)

            # 生成配置字典
            config_dict = self._config_to_dict(self.config)

            # 写入配置文件
            with open(self.config_file, "w", encoding="utf-8") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(
                    ".yml"
                ):
                    yaml.dump(
                        config_dict, f, default_flow_style=False, allow_unicode=True
                    )
                else:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)

            self.logger.info(f"创建默认配置文件成功: {self.config_file}")

        except Exception as e:
            self.logger.error(f"创建默认配置文件失败: {e}")

    def _config_to_dict(self, config_obj: Any, visited=None) -> dict[str, Any]:
        """将配置对象转换为字典"""
        if visited is None:
            visited = set()

        # 防止循环引用
        obj_id = id(config_obj)
        if obj_id in visited:
            return str(config_obj)

        visited.add(obj_id)

        if hasattr(config_obj, "__dict__"):
            result = {}
            for key, value in config_obj.__dict__.items():
                if key.startswith("_"):  # 跳过私有属性
                    continue
                if hasattr(value, "__dict__"):  # 嵌套配置对象
                    result[key] = self._config_to_dict(value, visited.copy())
                elif isinstance(value, Enum):
                    result[key] = value.value
                else:
                    result[key] = value
            return result
        else:
            return config_obj

    def _validate_config(self):
        """验证配置"""
        errors = []

        # 验证数据库配置
        if not self.config.database.host:
            errors.append("数据库主机不能为空")
        if self.config.database.port <= 0 or self.config.database.port > 65535:
            errors.append("数据库端口必须在1-65535之间")

        # 验证缓存配置
        if self.config.cache.default_ttl <= 0:
            errors.append("缓存TTL必须大于0")
        if self.config.cache.max_size <= 0:
            errors.append("缓存最大大小必须大于0")

        # 验证重试配置
        if self.config.akshare.retry.max_attempts <= 0:
            errors.append("最大重试次数必须大于0")
        if self.config.akshare.retry.base_delay <= 0:
            errors.append("基础延迟时间必须大于0")

        # 验证限流配置
        if self.config.akshare.rate_limit.requests_per_second <= 0:
            errors.append("每秒请求数必须大于0")

        if errors:
            error_msg = "配置验证失败:\n" + "\n".join(errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info("配置验证通过")

    def _setup_logging(self):
        """设置日志"""
        try:
            # 创建日志目录
            if self.config.logging.file_path:
                log_dir = Path(self.config.logging.file_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)

            # 配置根日志器
            root_logger = logging.getLogger()
            root_logger.setLevel(
                getattr(logging, self.config.logging.level.value))

            # 清除现有处理器
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # 创建格式器
            if self.config.logging.json_format:
                formatter = JsonFormatter()
            else:
                formatter = logging.Formatter(self.config.logging.format)

            # 添加控制台处理器
            if self.config.logging.console_output:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)

            # 添加文件处理器
            if self.config.logging.file_path:
                from logging.handlers import RotatingFileHandler

                file_handler = RotatingFileHandler(
                    self.config.logging.file_path,
                    maxBytes=self.config.logging.max_file_size,
                    backupCount=self.config.logging.backup_count,
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)

            self.logger.info("日志配置完成")

        except Exception as e:
            print(f"设置日志失败: {e}")

    def get_config(self) -> DataSourceConfig:
        """获取配置"""
        return self.config

    def update_config(self, updates: dict[str, Any]):
        """更新配置"""
        try:
            self._update_config_from_dict(self.config, updates)
            self._validate_config()
            self.logger.info("配置更新成功")
        except Exception as e:
            self.logger.error(f"配置更新失败: {e}")
            raise

    def save_config(self):
        """保存配置到文件"""
        try:
            config_dict = self._config_to_dict(self.config)

            with open(self.config_file, "w", encoding="utf-8") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(
                    ".yml"
                ):
                    yaml.dump(
                        config_dict, f, default_flow_style=False, allow_unicode=True
                    )
                else:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)

            self.logger.info(f"配置保存成功: {self.config_file}")

        except Exception as e:
            self.logger.error(f"配置保存失败: {e}")
            raise

    def reload_config(self):
        """重新加载配置"""
        try:
            self._load_config()
            self.logger.info("配置重新加载成功")
        except Exception as e:
            self.logger.error(f"配置重新加载失败: {e}")
            raise


class JsonFormatter(logging.Formatter):
    """JSON格式日志格式器"""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


# 全局配置管理器实例
_global_config_manager = None


def get_config_manager(config_file: str | None = None) -> ConfigManager:
    """
    获取全局配置管理器实例

    Args:
        config_file: 配置文件路径

    Returns:
        配置管理器实例
    """
    global _global_config_manager

    if _global_config_manager is None:
        _global_config_manager = ConfigManager(config_file)

    return _global_config_manager


def get_config() -> DataSourceConfig:
    """
    获取配置

    Returns:
        数据源配置
    """
    return get_config_manager().get_config()


# 配置验证装饰器
def validate_config(func):
    """配置验证装饰器"""

    def wrapper(*args, **kwargs):
        try:
            _ = get_config()
            return func(*args, **kwargs)
        except Exception as e:
            logging.getLogger(__name__).error(f"配置验证失败: {e}")
            raise

    return wrapper
