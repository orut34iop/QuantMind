import importlib
import logging
import os
import sys
from contextlib import contextmanager
from typing import Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

task_logger = StructuredTaskLogger(logger, "QlibUtils")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_bj_instrument(code: str) -> bool:
    code_str = str(code or "").upper()
    return code_str.startswith("BJ")


def exclude_bj_instruments(codes: list[str]) -> list[str]:
    return [c for c in codes if not is_bj_instrument(c)]


@contextmanager
def np_patch():
    """
    NumPy 2.0 兼容性补丁上下文管理器。
    处理由旧版 NumPy (1.26.x) 生成的 pickle 文件在 NumPy 2.0 环境下的加载问题。
    """
    patched_modules = {}
    # 如果当前是旧版 NumPy (1.x)，但读取由 2.x 生成的 pickle，或者反之
    # 核心映射：处理 numpy._core 找不到的问题
    if not hasattr(np, "_core") and hasattr(np, "core"):
        # NumPy 1.x 模拟 2.x 的路径
        if "numpy._core" not in sys.modules:
            patched_modules["numpy._core"] = sys.modules.get("numpy._core")
            sys.modules["numpy._core"] = np.core

            submodules = [
                "multiarray",
                "umath",
                "numeric",
                "fromnumeric",
                "defchararray",
                "records",
                "memmap",
                "function_base",
                "machar",
                "getlimits",
                "shape_base",
                "einsumfunc",
                "dtype",
                "scalar",
            ]
            for sub in submodules:
                target = f"numpy._core.{sub}"
                if target not in sys.modules:
                    source = getattr(np.core, sub, None) or getattr(np, sub, None)
                    if source:
                        patched_modules[target] = sys.modules.get(target)
                        sys.modules[target] = source
    elif hasattr(np, "_core") and "numpy.core" not in sys.modules:
        # NumPy 2.x 模拟 1.x 的路径 (虽然通常 2.x 会自带兼容，但这里作为双重保险)
        sys.modules["numpy.core"] = np._core
        patched_modules["numpy.core"] = None

    try:
        yield
    finally:
        # 恢复环境
        for mod, old_val in reversed(patched_modules.items()):
            if old_val is None:
                if mod in sys.modules:
                    del sys.modules[mod]
            else:
                sys.modules[mod] = old_val


def safe_backtest(*args, **kwargs):
    """
    兼容性封装的 qlib backtest 函数。
    自动过滤在不同 Qlib 版本间可能引起冲突的参数。
    """
    if "server" in kwargs:
        task_logger.debug("safe_backtest_filter_legacy", "过滤掉 legacy 参数 server")
        kwargs.pop("server")

    try:
        from qlib.backtest import backtest as q_backtest

        return q_backtest(*args, **kwargs)
    except Exception as e:
        task_logger.error("safe_backtest_failed", "safe_backtest 执行失败", error=str(e))
        raise


def resolve_qlib_backend(allow_mock: bool = None) -> tuple[Any, Any, Any, str]:
    """Resolve Qlib backend (real or mock)"""
    use_mock = env_bool("ENGINE_ALLOW_MOCK_QLIB", False) if allow_mock is None else allow_mock
    try:
        qlib_mod = importlib.import_module("qlib")
        # 优先使用包装后的 backtest
        backtest_fn = safe_backtest
        d_obj = importlib.import_module("qlib.data").D
        task_logger.info("backend_resolved", "使用真实 qlib 模块 (通过 safe_backtest 封装)", backend="real")
        return qlib_mod, backtest_fn, d_obj, "real"
    except Exception as real_err:
        if not use_mock:
            task_logger.error(
                "real_backend_unavailable",
                "真实 qlib 不可用且 ENGINE_ALLOW_MOCK_QLIB=false，拒绝回退到 mock",
                error=str(real_err),
            )
            raise ImportError("真实 qlib 不可用且 ENGINE_ALLOW_MOCK_QLIB=false，已禁用 mock 回退") from real_err

        mock_mod = importlib.import_module("backend.services.engine.qlib_mock")
        task_logger.warning("backend_fallback_mock", "真实 qlib 不可用，已启用 mock qlib", backend="mock")
        return mock_mod, mock_mod.backtest, mock_mod.D, "mock"


# Global instance for easy import
# 强制加载真实的 qlib，不再静默捕获 ImportError
# 如果加载失败，让进程在启动阶段就崩溃，暴露出底层的系统依赖或环境问题
qlib, backtest, D, QLIB_BACKEND = resolve_qlib_backend()
