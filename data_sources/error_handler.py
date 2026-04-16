#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误处理模块
提供统一的异常处理和错误恢复机制
"""

import asyncio
import functools
import logging
import random
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type


class ErrorSeverity(Enum):
    """错误严重程度"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""

    NETWORK = "network"
    DATABASE = "database"
    API = "api"
    DATA = "data"
    SYSTEM = "system"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """错误信息"""

    error_type: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: float
    traceback: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    recoverable: bool = True


class DataSourceError(Exception):
    """数据源基础异常"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.recoverable = recoverable
        self.timestamp = time.time()


class NetworkError(DataSourceError):
    """网络错误"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.NETWORK, **kwargs)
        self.status_code = status_code
        self.url = url
        self.context.update({"status_code": status_code, "url": url})


class DatabaseError(DataSourceError):
    """数据库错误"""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        table: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.DATABASE, **kwargs)
        self.query = query
        self.table = table
        self.context.update({"query": query, "table": table})


class APIError(DataSourceError):
    """API错误"""

    def __init__(
        self,
        message: str,
        api_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        response_code: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.API, **kwargs)
        self.api_name = api_name
        self.endpoint = endpoint
        self.response_code = response_code
        self.context.update(
<<<<<<< HEAD
            {"api_name": api_name, "endpoint": endpoint, "response_code": response_code}
=======
            {"api_name": api_name, "endpoint": endpoint,
                "response_code": response_code}
>>>>>>> refactor/service-cleanup
        )


class DataValidationError(DataSourceError):
    """数据验证错误"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ):
        super().__init__(
            message, ErrorCategory.VALIDATION, ErrorSeverity.HIGH, **kwargs
        )
        self.field = field
        self.value = value
        self.context.update(
<<<<<<< HEAD
            {"field": field, "value": str(value) if value is not None else None}
=======
            {"field": field, "value": str(
                value) if value is not None else None}
>>>>>>> refactor/service-cleanup
        )


class RateLimitError(DataSourceError):
    """限流错误"""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(
            message, ErrorCategory.RATE_LIMIT, ErrorSeverity.MEDIUM, **kwargs
        )
        self.retry_after = retry_after
        self.context.update({"retry_after": retry_after})


class TimeoutError(DataSourceError):
    """超时错误"""

    def __init__(
        self, message: str, timeout_duration: Optional[float] = None, **kwargs
    ):
        super().__init__(message, ErrorCategory.TIMEOUT, ErrorSeverity.MEDIUM, **kwargs)
        self.timeout_duration = timeout_duration
        self.context.update({"timeout_duration": timeout_duration})


class AuthenticationError(DataSourceError):
    """认证错误"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            ErrorCategory.AUTHENTICATION,
            ErrorSeverity.HIGH,
            recoverable=False,
            **kwargs,
        )


class PermissionError(DataSourceError):
    """权限错误"""

    def __init__(self, message: str, resource: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            ErrorCategory.PERMISSION,
            ErrorSeverity.HIGH,
            recoverable=False,
            **kwargs,
        )
        self.resource = resource
        self.context.update({"resource": resource})


class ErrorHandler:
    """错误处理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_history: List[ErrorInfo] = []
        self.error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {}

        # 注册默认恢复策略
        self._register_default_strategies()

    def _register_default_strategies(self):
        """注册默认恢复策略"""
        self.recovery_strategies[ErrorCategory.NETWORK] = self._handle_network_error
        self.recovery_strategies[ErrorCategory.DATABASE] = self._handle_database_error
        self.recovery_strategies[ErrorCategory.API] = self._handle_api_error
        self.recovery_strategies[ErrorCategory.RATE_LIMIT] = (
            self._handle_rate_limit_error
        )
        self.recovery_strategies[ErrorCategory.TIMEOUT] = self._handle_timeout_error

    def handle_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> ErrorInfo:
        """处理错误"""
        # 创建错误信息
        error_info = self._create_error_info(error, context)

        # 记录错误
        self._log_error(error_info)

        # 添加到历史记录
        self.error_history.append(error_info)

        # 执行回调
        self._execute_callbacks(error_info)

        # 尝试恢复
        if error_info.recoverable:
            self._attempt_recovery(error_info)

        return error_info

    def _create_error_info(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> ErrorInfo:
        """创建错误信息"""
        if isinstance(error, DataSourceError):
            return ErrorInfo(
                error_type=type(error).__name__,
                message=error.message,
                category=error.category,
                severity=error.severity,
                timestamp=error.timestamp,
                traceback=traceback.format_exc(),
                context={**(error.context or {}), **(context or {})},
                recoverable=error.recoverable,
            )
        else:
            # 根据异常类型推断类别
            category = self._infer_error_category(error)
            severity = self._infer_error_severity(error)

            return ErrorInfo(
                error_type=type(error).__name__,
                message=str(error),
                category=category,
                severity=severity,
                timestamp=time.time(),
                traceback=traceback.format_exc(),
                context=context or {},
                recoverable=True,
            )

    def _infer_error_category(self, error: Exception) -> ErrorCategory:
        """推断错误类别"""
        error_name = type(error).__name__.lower()

        if (
            "network" in error_name
            or "connection" in error_name
            or "http" in error_name
        ):
            return ErrorCategory.NETWORK
        elif "database" in error_name or "sql" in error_name:
            return ErrorCategory.DATABASE
        elif "timeout" in error_name:
            return ErrorCategory.TIMEOUT
        elif "permission" in error_name or "access" in error_name:
            return ErrorCategory.PERMISSION
        elif "auth" in error_name:
            return ErrorCategory.AUTHENTICATION
        elif "validation" in error_name or "value" in error_name:
            return ErrorCategory.VALIDATION
        else:
            return ErrorCategory.UNKNOWN

    def _infer_error_severity(self, error: Exception) -> ErrorSeverity:
        """推断错误严重程度"""
        error_name = type(error).__name__.lower()

        if "critical" in error_name or "fatal" in error_name:
            return ErrorSeverity.CRITICAL
        elif "permission" in error_name or "auth" in error_name:
            return ErrorSeverity.HIGH
        elif "timeout" in error_name or "network" in error_name:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW

    def _log_error(self, error_info: ErrorInfo):
        """记录错误日志"""
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }.get(error_info.severity, logging.ERROR)

        self.logger.log(
            log_level,
            f"[{error_info.category.value.upper()}] {error_info.error_type}: {error_info.message}",
            extra={"error_info": error_info, "context": error_info.context},
        )

        if error_info.traceback and error_info.severity in [
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL,
        ]:
            self.logger.debug(f"Traceback:\n{error_info.traceback}")

    def _execute_callbacks(self, error_info: ErrorInfo):
        """执行错误回调"""
        callbacks = self.error_callbacks.get(error_info.category, [])
        for callback in callbacks:
            try:
                callback(error_info)
            except Exception as e:
                self.logger.error(f"执行错误回调失败: {e}")

    def _attempt_recovery(self, error_info: ErrorInfo):
        """尝试错误恢复"""
        strategy = self.recovery_strategies.get(error_info.category)
        if strategy:
            try:
                strategy(error_info)
            except Exception as e:
                self.logger.error(f"错误恢复失败: {e}")

    def _handle_network_error(self, error_info: ErrorInfo):
        """处理网络错误"""
        self.logger.info(f"尝试网络错误恢复: {error_info.message}")
        # 可以实现网络重连逻辑

    def _handle_database_error(self, error_info: ErrorInfo):
        """处理数据库错误"""
        self.logger.info(f"尝试数据库错误恢复: {error_info.message}")
        # 可以实现数据库重连逻辑

    def _handle_api_error(self, error_info: ErrorInfo):
        """处理API错误"""
        self.logger.info(f"尝试API错误恢复: {error_info.message}")
        # 可以实现API重试逻辑

    def _handle_rate_limit_error(self, error_info: ErrorInfo):
        """处理限流错误"""
        retry_after = error_info.context.get("retry_after", 60)
        self.logger.info(f"遇到限流，等待 {retry_after} 秒后重试")
        time.sleep(retry_after)

    def _handle_timeout_error(self, error_info: ErrorInfo):
        """处理超时错误"""
        self.logger.info(f"遇到超时错误，准备重试: {error_info.message}")
        # 可以实现超时重试逻辑

    def register_callback(
        self, category: ErrorCategory, callback: Callable[[ErrorInfo], None]
    ):
        """注册错误回调"""
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)

    def register_recovery_strategy(
        self, category: ErrorCategory, strategy: Callable[[ErrorInfo], None]
    ):
        """注册恢复策略"""
        self.recovery_strategies[category] = strategy

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        if not self.error_history:
            return {}

        total_errors = len(self.error_history)
        category_counts = {}
        severity_counts = {}

        for error_info in self.error_history:
            category_counts[error_info.category.value] = (
                category_counts.get(error_info.category.value, 0) + 1
            )
            severity_counts[error_info.severity.value] = (
                severity_counts.get(error_info.severity.value, 0) + 1
            )

        return {
            "total_errors": total_errors,
            "category_distribution": category_counts,
            "severity_distribution": severity_counts,
            "recent_errors": [
                {
                    "type": error.error_type,
                    "message": error.message,
                    "category": error.category.value,
                    "severity": error.severity.value,
                    "timestamp": error.timestamp,
                }
                for error in self.error_history[-10:]
            ],  # 最近10个错误
        }

    def clear_error_history(self):
        """清除错误历史"""
        self.error_history.clear()
        self.logger.info("错误历史已清除")


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[List[Type[Exception]]] = None,
):
    """重试装饰器"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否应该重试
                    if retry_on and not any(
                        isinstance(e, exc_type) for exc_type in retry_on
                    ):
                        raise

                    if attempt == max_retries:
                        break

                        # 计算延迟时间
                    wait_time = delay * (backoff_factor**attempt)
                    if jitter:
                        wait_time *= 0.5 + random.random() * 0.5  # 添加抖动

                    logging.getLogger(__name__).warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{wait_time:.2f}秒后重试"
                    )

                    time.sleep(wait_time)

                    # 所有重试都失败了
            logging.getLogger(__name__).error(
                f"函数 {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
            )
            raise last_exception

        return wrapper

    return decorator


def async_retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[List[Type[Exception]]] = None,
):
    """异步重试装饰器"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否应该重试
                    if retry_on and not any(
                        isinstance(e, exc_type) for exc_type in retry_on
                    ):
                        raise

                    if attempt == max_retries:
                        break

                        # 计算延迟时间
                    wait_time = delay * (backoff_factor**attempt)
                    if jitter:
                        wait_time *= 0.5 + random.random() * 0.5  # 添加抖动

                    logging.getLogger(__name__).warning(
                        f"异步函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {e}，{wait_time:.2f}秒后重试"
                    )

                    await asyncio.sleep(wait_time)

                    # 所有重试都失败了
            logging.getLogger(__name__).error(
                f"异步函数 {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
            )
            raise last_exception

        return wrapper

    return decorator


def handle_errors(
    error_handler: Optional[ErrorHandler] = None,
    reraise: bool = True,
    default_return: Any = None,
):
    """错误处理装饰器"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = error_handler or get_global_error_handler()
                handler.handle_error(
                    e,
                    {
                        "function": func.__name__,
                        "args": str(args)[:200],  # 限制长度
                        "kwargs": str(kwargs)[:200],
                    },
                )

                if reraise:
                    raise
                else:
                    return default_return

        return wrapper

    return decorator

    # 全局错误处理器实例


_global_error_handler = None


def get_global_error_handler() -> ErrorHandler:
    """获取全局错误处理器"""
    global _global_error_handler

    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()

    return _global_error_handler


def set_global_error_handler(handler: ErrorHandler):
    """设置全局错误处理器"""
    global _global_error_handler
    _global_error_handler = handler

    # 便捷函数


def handle_error(
    error: Exception, context: Optional[Dict[str, Any]] = None
) -> ErrorInfo:
    """处理错误的便捷函数"""
    return get_global_error_handler().handle_error(error, context)


def get_error_statistics() -> Dict[str, Any]:
    """获取错误统计信息的便捷函数"""
    return get_global_error_handler().get_error_statistics()


def clear_error_history():
    """清除错误历史的便捷函数"""
    get_global_error_handler().clear_error_history()
