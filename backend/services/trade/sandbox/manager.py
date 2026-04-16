import multiprocessing as mp
import os
import signal
import time
import uuid
from typing import Dict, Optional

from backend.services.trade.sandbox.worker import sandbox_worker_main
from backend.shared.logging_config import get_logger

logger = get_logger(__name__)


class SandboxPlatformManager:
    """
    轻量级沙箱进程池管理器。
    负责拉起、维护一定数量的 Worker 进程，提供提交运行任务、停止运行任务的接口。
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, pool_size: int = 10):
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.pool_size = pool_size
        self._workers: dict[int, mp.Process] = {}
        self._task_queues: dict[int, mp.Queue] = {}

        # 记录每个 run_id 由哪个 worker pid 在执行
        self._active_runs: dict[str, int] = {}
        self._initialized = True

    def start_pool(self):
        """拉起进程池"""
        logger.info(f"Starting Sandbox Worker Pool with {self.pool_size} workers...")

        for i in range(self.pool_size):
            q = mp.Queue()
            p = mp.Process(target=sandbox_worker_main, args=(q,), daemon=True)
            p.start()
            self._workers[p.pid] = p
            self._task_queues[p.pid] = q

        logger.info(f"Sandbox Worker Pool started. PIDs: {list(self._workers.keys())}")

    def stop_pool(self):
        """关闭所有 worker"""
        logger.info("Stopping Sandbox Worker Pool...")
        for pid, q in self._task_queues.items():
            q.put(None)  # 发送毒药

        for pid, p in self._workers.items():
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()

        self._workers.clear()
        self._task_queues.clear()
        self._active_runs.clear()
        logger.info("Sandbox Worker Pool stopped.")

    def submit_strategy(
        self,
        tenant_id: str,
        user_id: str,
        strategy_id: str,
        code_str: str,
        exec_config: dict,
        live_trade_config: dict | None = None,
    ) -> str:
        """分发策略到其中一个空闲的 Worker，返回 run_id"""
        # 简单的随机/轮询找一个没满的工作队列，或者粗略绑定
        # 为了简单，当前找到队列中最空闲或直接随便选一个
        # 在真实高并发场景，需要跟踪 worker 的 busy 状态

        # 随机哈希一个 pid
        pids = list(self._workers.keys())
        if not pids:
            raise RuntimeError("Sandbox Worker Pool is empty.")

        run_id = str(uuid.uuid4())

        # 找出活跃度最低的 (简单拿 keys，这里没做精确空闲判定)
        assigned_pid = pids[hash(user_id) % len(pids)]

        task = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "strategy_id": strategy_id,
            "run_id": run_id,
            "code_str": code_str,
            "exec_config": exec_config,
            "live_trade_config": live_trade_config or {},
        }

        self._task_queues[assigned_pid].put(task)
        self._active_runs[f"{tenant_id}_{user_id}_{strategy_id}"] = assigned_pid
        logger.info(
            f"Submitted simulation strategy {strategy_id} for user {user_id} to Sandbox Process PID {assigned_pid}"
        )
        return run_id

    def stop_strategy(self, tenant_id: str, user_id: str, strategy_id: str) -> bool:
        """请求停止策略：由于当前一个进程在阻塞循环，停止的最暴力/安全方式是杀掉那个进程然后起一个替补"""
        key = f"{tenant_id}_{user_id}_{strategy_id}"
        if key not in self._active_runs:
            logger.warning(f"Strategy {strategy_id} is not tracked as running in sandbox.")
            return False

        pid = self._active_runs[key]
        if pid in self._workers:
            p = self._workers[pid]
            # 杀掉重起
            os.kill(pid, signal.SIGTERM)
            p.join(timeout=2)
            if p.is_alive():
                os.kill(pid, signal.SIGKILL)

            # 移除旧的，补一个新的
            del self._workers[pid]
            q = self._task_queues.pop(pid)

            logger.info(f"Sandbox Worker {pid} killed for stopping strategy {strategy_id}. Respawning a new worker.")

            new_q = mp.Queue()
            new_p = mp.Process(target=sandbox_worker_main, args=(new_q,), daemon=True)
            new_p.start()
            self._workers[new_p.pid] = new_p
            self._task_queues[new_p.pid] = new_q

            del self._active_runs[key]
            return True
        return False


sandbox_manager = SandboxPlatformManager()
