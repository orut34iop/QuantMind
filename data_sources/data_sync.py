#!/usr/bin/env python3
"""
数据同步和更新机制
用于弥补本地数据缺失，自动同步和更新数据
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from collections.abc import Callable

from .akshare_api import AkShareAPI

# 导入数据管理器
from .data_manager import get_data_manager


class SyncStatus(Enum):
    """同步状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncType(Enum):
    """同步类型枚举"""

    FULL = "full"  # 全量同步
    INCREMENTAL = "incremental"  # 增量同步
    REALTIME = "realtime"  # 实时同步
    SCHEDULED = "scheduled"  # 定时同步


@dataclass
class SyncTask:
    """同步任务数据类"""

    id: str
    name: str
    sync_type: SyncType
    data_source: str
    parameters: dict[str, Any]
    schedule: str | None = None  # cron表达式
    status: SyncStatus = SyncStatus.PENDING
    created_at: datetime = None
    updated_at: datetime = None
    last_run: datetime | None = None
    next_run: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class DataSyncManager:
    """
    数据同步管理器
    负责管理和执行数据同步任务
    """

    def __init__(self, config: dict | None = None):
        """
        初始化数据同步管理器

        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 初始化组件
        try:
            self.data_manager = get_data_manager(
                self.config.get("data_manager", {}))
        except Exception as e:
            self.logger.warning(f"数据管理器初始化失败，使用默认配置: {e}")
            self.data_manager = None

        try:
            self.akshare_api = AkShareAPI(self.config.get("akshare", {}))
        except Exception as e:
            self.logger.warning(f"AkShare API初始化失败: {e}")
            self.akshare_api = None

        # 同步任务存储
        self.tasks: dict[str, SyncTask] = {}
        self.running_tasks: dict[str, asyncio.Task] = {}

        # 初始化线程池
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 4)
        )

        # 同步状态
        self.is_running = False
        self.scheduler_task = None

        # 数据库连接（用于持久化任务，仅 PostgreSQL）
        self.db_url = self.config.get(
            "db_url",
            "postgresql+psycopg2://postgres:@localhost:5432/quantmind",
        )
        try:
            self._init_database()
        except Exception as e:
            self.logger.warning(f"数据库初始化失败: {e}")
            # 使用默认 PostgreSQL 连接作为备选
            self.db_url = "postgresql+psycopg2://postgres:@localhost:5432/quantmind"
            self._init_database()

        # 回调函数
        self.callbacks: dict[str, list[Callable]] = {
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "data_updated": [],
        }

        # 数据缺失检测配置
        self.gap_detection_enabled = self.config.get(
            "gap_detection_enabled", True)
        self.gap_check_interval = self.config.get(
            "gap_check_interval", 3600)  # 1小时

        # 加载已保存的任务
        self._load_tasks_from_db()

    def _init_database(self):
        """初始化数据库"""
        try:
            # 这里需要导入 SQLAlchemy 或其他 PostgreSQL 连接库
            # 暂时使用日志记录，实际使用时需要实现 PostgreSQL 连接
            self.logger.info(f"PostgreSQL数据库连接已配置: {self.db_url}")
            self.logger.info("注意：需要实现PostgreSQL数据库连接逻辑")

        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise

    def _load_tasks_from_db(self):
        """从数据库加载任务"""
        try:
            # 使用 PostgreSQL 数据库连接
            # 这里需要实现 PostgreSQL 连接逻辑
            self.logger.info("从PostgreSQL数据库加载任务")
            # 暂时返回空列表，实际使用时需要实现 PostgreSQL 查询
            return []

        except Exception as e:
            self.logger.error(f"从数据库加载任务失败: {e}")

    def _save_task_to_db(self, task: SyncTask):
        """保存任务到数据库"""
        try:
            # 使用 PostgreSQL 数据库连接
            # 这里需要实现 PostgreSQL 数据库连接逻辑
            self.logger.info(f"保存任务到PostgreSQL数据库: {task.name}")
            # 暂时记录日志，实际使用时需要实现 PostgreSQL 插入逻辑
        except Exception as e:
            self.logger.error(f"保存任务到数据库失败: {e}")

    def _log_sync_result(
        self,
        task_id: str,
        status: SyncStatus,
        message: str = None,
        data_count: int = 0,
        duration: float = 0,
    ):
        """记录同步结果"""
        try:
            # 使用 PostgreSQL 数据库连接
            # 这里需要实现 PostgreSQL 数据库连接逻辑
            self.logger.info(f"记录同步结果到PostgreSQL数据库: {task_id}, {status.value}")
            # 暂时记录日志，实际使用时需要实现 PostgreSQL 插入逻辑
        except Exception as e:
            self.logger.error(f"记录同步结果失败: {e}")

    def add_task(self, task: SyncTask) -> bool:
        """
        添加同步任务

        Args:
            task: 同步任务

        Returns:
            是否添加成功
        """
        try:
            if task.id in self.tasks:
                self.logger.warning(f"任务{task.id}已存在")
                return False

            # 计算下次运行时间
            if task.schedule:
                task.next_run = self._calculate_next_run(task.schedule)

            self.tasks[task.id] = task
            self._save_task_to_db(task)

            self.logger.info(f"添加同步任务成功: {task.name}")
            return True

        except Exception as e:
            self.logger.error(f"添加同步任务失败: {e}")
            return False

    def create_sync_task(
        self,
        name: str,
        sync_type: str,
        data_source: str,
        parameters: dict[str, Any],
        schedule: str = None,
    ) -> str:
        """
        创建同步任务

        Args:
            name: 任务名称
            sync_type: 同步类型
            data_source: 数据源
            parameters: 参数
            schedule: 调度表达式

        Returns:
            任务ID
        """
        try:
            task_id = f"{data_source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            task = SyncTask(
                id=task_id,
                name=name,
                sync_type=SyncType(sync_type),
                data_source=data_source,
                parameters=parameters,
                schedule=schedule,
            )

            success = self.add_task(task)
            return task_id if success else None

        except Exception as e:
            self.logger.error(f"创建同步任务失败: {e}")
            return None

    def update_sync_task(self, task_id: str, **kwargs) -> bool:
        """
        更新同步任务

        Args:
            task_id: 任务ID
            **kwargs: 更新的字段

        Returns:
            是否更新成功
        """
        try:
            if task_id not in self.tasks:
                self.logger.warning(f"任务{task_id}不存在")
                return False

            task = self.tasks[task_id]

            # 更新字段
            for key, value in kwargs.items():
                if hasattr(task, key):
                    if key == "sync_type" and isinstance(value, str):
                        setattr(task, key, SyncType(value))
                    elif key == "status" and isinstance(value, str):
                        setattr(task, key, SyncStatus(value))
                    else:
                        setattr(task, key, value)

            task.updated_at = datetime.now()
            self._save_task_to_db(task)

            self.logger.info(f"更新同步任务成功: {task_id}")
            return True

        except Exception as e:
            self.logger.error(f"更新同步任务失败: {e}")
            return False

    def remove_task(self, task_id: str) -> bool:
        """
        移除同步任务

        Args:
            task_id: 任务ID

        Returns:
            是否移除成功
        """
        try:
            if task_id not in self.tasks:
                self.logger.warning(f"任务{task_id}不存在")
                return False

            # 停止正在运行的任务
            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                del self.running_tasks[task_id]

            # 从内存中删除
            del self.tasks[task_id]

            # 使用MySQL数据库连接
            # 这里需要实现MySQL数据库删除逻辑
            self.logger.info(f"从MySQL数据库移除任务: {task_id}")

            self.logger.info(f"移除同步任务成功: {task_id}")
            return True

        except Exception as e:
            self.logger.error(f"移除同步任务失败: {e}")
            return False

    def delete_sync_task(self, task_id: str) -> bool:
        """删除同步任务（别名方法）"""
        return self.remove_task(task_id)

    def execute_sync_task(self, task_id: str) -> bool:
        """执行同步任务"""
        try:
            if task_id not in self.tasks:
                self.logger.error(f"任务不存在: {task_id}")
                return False

            task = self.tasks[task_id]
            self.logger.info(f"开始执行同步任务: {task.name}")

            # 执行任务逻辑
            success = self._execute_task(task)

            # 记录执行结果
            self._log_sync_result(
                task_id=task_id,
                status=SyncStatus.COMPLETED if success else SyncStatus.FAILED,
                message="任务执行完成" if success else "任务执行失败",
                data_count=0,
                duration=0,
            )

            return success
        except Exception as e:
            self.logger.error(f"执行同步任务失败: {e}")
            return False

    def _execute_task(self, task: SyncTask) -> bool:
        """执行具体任务逻辑"""
        try:
            # 根据数据源类型执行不同的同步逻辑
            if task.data_source == "stock_list":
                # 模拟股票列表同步
                self.logger.info(f"同步股票列表: {task.parameters}")
                return True
            elif task.data_source == "realtime_data":
                # 模拟实时数据同步
                self.logger.info(f"同步实时数据: {task.parameters}")
                return True
            elif task.data_source == "historical_data":
                # 模拟历史数据同步
                self.logger.info(f"同步历史数据: {task.parameters}")
                return True
            else:
                self.logger.warning(f"未知的数据源类型: {task.data_source}")
                return False
        except Exception as e:
            self.logger.error(f"执行任务逻辑失败: {e}")
            return False

    async def run_task(self, task_id: str) -> bool:
        """
        运行同步任务

        Args:
            task_id: 任务ID

        Returns:
            是否运行成功
        """
        if task_id not in self.tasks:
            self.logger.error(f"任务{task_id}不存在")
            return False

        task = self.tasks[task_id]

        if task.status == SyncStatus.RUNNING:
            self.logger.warning(f"任务{task_id}正在运行中")
            return False

        try:
            # 更新任务状态
            task.status = SyncStatus.RUNNING
            task.last_run = datetime.now()
            task.updated_at = datetime.now()
            self._save_task_to_db(task)

            # 触发回调
            await self._trigger_callbacks("task_started", task)

            start_time = datetime.now()
            data_count = 0

            # 根据数据源类型执行同步
            if task.data_source == "stock_list":
                data_count = await self._sync_stock_list(task)
            elif task.data_source == "realtime_data":
                data_count = await self._sync_realtime_data(task)
            elif task.data_source == "historical_data":
                data_count = await self._sync_historical_data(task)
            elif task.data_source == "market_overview":
                data_count = await self._sync_market_overview(task)
            else:
                raise ValueError(f"不支持的数据源: {task.data_source}")

            # 计算执行时间
            duration = (datetime.now() - start_time).total_seconds()

            # 更新任务状态
            task.status = SyncStatus.COMPLETED
            task.retry_count = 0
            task.error_message = None

            # 计算下次运行时间
            if task.schedule:
                task.next_run = self._calculate_next_run(task.schedule)

            task.updated_at = datetime.now()
            self._save_task_to_db(task)

            # 记录同步结果
            self._log_sync_result(
                task_id,
                SyncStatus.COMPLETED,
                f"同步完成，处理{data_count}条数据",
                data_count,
                duration,
            )

            # 触发回调
            await self._trigger_callbacks("task_completed", task)
            await self._trigger_callbacks(
                "data_updated", {"task": task, "data_count": data_count}
            )

            self.logger.info(
                f"任务{task.name}执行成功，处理{data_count}条数据，耗时{duration:.2f}秒"
            )
            return True

        except Exception as e:
            # 更新任务状态
            task.status = SyncStatus.FAILED
            task.retry_count += 1
            task.error_message = str(e)
            task.updated_at = datetime.now()
            self._save_task_to_db(task)

            # 记录同步结果
            duration = (datetime.now() - start_time).total_seconds()
            self._log_sync_result(
                task_id, SyncStatus.FAILED, str(e), 0, duration)

            # 触发回调
            await self._trigger_callbacks("task_failed", task)

            self.logger.error(f"任务{task.name}执行失败: {e}")

            # 如果未达到最大重试次数，安排重试
            if task.retry_count < task.max_retries:
                retry_delay = min(
                    300 * (2**task.retry_count), 3600
                )  # 指数退避，最大1小时
                task.next_run = datetime.now() + timedelta(seconds=retry_delay)
                task.status = SyncStatus.PENDING
                self._save_task_to_db(task)

                self.logger.info(f"任务{task.name}将在{retry_delay}秒后重试")

            return False

        finally:
            # 清理运行中的任务记录
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

    async def _sync_stock_list(self, task: SyncTask) -> int:
        """同步股票列表"""
        market = task.parameters.get("market", "all")
        data = await self.data_manager.get_stock_list(market, use_cache=False)

        if data is not None:
            # 这里可以添加数据存储逻辑
            return len(data)

        return 0

    async def _sync_realtime_data(self, task: SyncTask) -> int:
        """同步实时数据"""
        symbols = task.parameters.get("symbols", [])
        if not symbols:
            return 0

        data = await self.data_manager.get_realtime_data(symbols, use_cache=False)

        # 统计成功获取的数据数量
        success_count = len([v for v in data.values() if v is not None])
        return success_count

    async def _sync_historical_data(self, task: SyncTask) -> int:
        """同步历史数据"""
        symbol = task.parameters.get("symbol")
        period = task.parameters.get("period", "1y")
        start_date = task.parameters.get("start_date")
        end_date = task.parameters.get("end_date")

        if not symbol:
            return 0

        data = await self.data_manager.get_historical_data(
            symbol, period, start_date, end_date, use_cache=False
        )

        if data is not None:
            return len(data)

        return 0

    async def _sync_market_overview(self, task: SyncTask) -> int:
        """同步市场概览"""
        data = await self.data_manager.get_market_overview(use_cache=False)

        if data is not None:
            return 1  # 市场概览是单条记录

        return 0

    def _calculate_next_run(self, schedule: str) -> datetime:
        """
        计算下次运行时间（简化的cron实现）

        Args:
            schedule: 调度表达式

        Returns:
            下次运行时间
        """
        # 这里实现简化的调度逻辑
        # 支持格式: "every_5m", "every_1h", "every_1d", "daily_09:30"

        now = datetime.now()

        if schedule.startswith("every_"):
            interval_str = schedule[6:]

            if interval_str.endswith("m"):
                minutes = int(interval_str[:-1])
                return now + timedelta(minutes=minutes)
            elif interval_str.endswith("h"):
                hours = int(interval_str[:-1])
                return now + timedelta(hours=hours)
            elif interval_str.endswith("d"):
                days = int(interval_str[:-1])
                return now + timedelta(days=days)

        elif schedule.startswith("daily_"):
            time_str = schedule[6:]
            hour, minute = map(int, time_str.split(":"))

            next_run = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

            return next_run

        # 默认1小时后
        return now + timedelta(hours=1)

    async def _trigger_callbacks(self, event: str, data: Any):
        """触发回调函数"""
        try:
            for callback in self.callbacks.get(event, []):
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
        except Exception as e:
            self.logger.error(f"触发回调失败: {e}")

    def add_callback(self, event: str, callback: Callable):
        """添加回调函数"""
        if event not in self.callbacks:
            self.callbacks[event] = []

        self.callbacks[event].append(callback)

    async def start_scheduler(self):
        """启动调度器"""
        if self.is_running:
            self.logger.warning("调度器已在运行中")
            return

        self.is_running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())

        self.logger.info("数据同步调度器已启动")

    async def stop_scheduler(self):
        """停止调度器"""
        if not self.is_running:
            return

        self.is_running = False

        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

        # 取消所有运行中的任务
        for task in self.running_tasks.values():
            task.cancel()

        self.running_tasks.clear()

        self.logger.info("数据同步调度器已停止")

    async def _scheduler_loop(self):
        """调度器主循环"""
        while self.is_running:
            try:
                now = datetime.now()

                # 检查需要运行的任务
                for task_id, task in self.tasks.items():
                    if (
                        task.status == SyncStatus.PENDING
                        and task.next_run
                        and task.next_run <= now
                        and task_id not in self.running_tasks
                    ):
                        # 创建异步任务
                        async_task = asyncio.create_task(
                            self.run_task(task_id))
                        self.running_tasks[task_id] = async_task

                # 清理已完成的任务
                completed_tasks = []
                for task_id, async_task in self.running_tasks.items():
                    if async_task.done():
                        completed_tasks.append(task_id)

                for task_id in completed_tasks:
                    del self.running_tasks[task_id]

                # 等待下次检查
                await asyncio.sleep(60)  # 每分钟检查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"调度器循环出错: {e}")
                await asyncio.sleep(60)

    def get_task_status(self, task_id: str) -> dict | None:
        """获取任务状态"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        return {
            "id": task.id,
            "name": task.name,
            "status": task.status.value,
            "last_run": task.last_run.isoformat() if task.last_run else None,
            "next_run": task.next_run.isoformat() if task.next_run else None,
            "retry_count": task.retry_count,
            "error_message": task.error_message,
        }

    def get_all_tasks_status(self) -> list[dict]:
        """获取所有任务状态"""
        return [self.get_task_status(task_id) for task_id in self.tasks.keys()]

    async def detect_data_gaps(self) -> list[dict]:
        """
        检测数据缺失

        Returns:
            缺失数据列表
        """
        gaps = []

        try:
            # 这里可以实现具体的数据缺失检测逻辑
            # 例如检查历史数据的连续性、实时数据的更新频率等

            # 示例：检查股票列表是否需要更新
            stock_list_task = None
            for task in self.tasks.values():
                if task.data_source == "stock_list":
                    stock_list_task = task
                    break

            if stock_list_task and stock_list_task.last_run:
                time_since_last_run = datetime.now() - stock_list_task.last_run
                if time_since_last_run > timedelta(days=1):
                    gaps.append(
                        {
                            "type": "stock_list",
                            "description": "股票列表超过1天未更新",
                            "last_update": stock_list_task.last_run.isoformat(),
                            "suggested_action": "运行股票列表同步任务",
                        }
                    )

            return gaps

        except Exception as e:
            self.logger.error(f"检测数据缺失失败: {e}")
            return []

    async def auto_fill_gaps(self) -> dict[str, Any]:
        """
        自动填补数据缺失

        Returns:
            填补结果
        """
        try:
            gaps = await self.detect_data_gaps()

            if not gaps:
                return {
                    "status": "success",
                    "message": "未发现数据缺失",
                    "filled_gaps": 0,
                }

            filled_count = 0

            for gap in gaps:
                if gap["type"] == "stock_list":
                    # 创建临时同步任务
                    temp_task = SyncTask(
                        id=f"temp_stock_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        name="临时股票列表同步",
                        sync_type=SyncType.FULL,
                        data_source="stock_list",
                        parameters={"market": "all"},
                    )

                    success = await self.run_task(temp_task.id)
                    if success:
                        filled_count += 1

            return {
                "status": "success",
                "message": f"成功填补{filled_count}个数据缺失",
                "filled_gaps": filled_count,
                "total_gaps": len(gaps),
            }

        except Exception as e:
            self.logger.error(f"自动填补数据缺失失败: {e}")
            return {"status": "error", "message": str(e), "filled_gaps": 0}


# 全局同步管理器实例
_global_sync_manager = None


def get_sync_manager(config: dict | None = None) -> DataSyncManager:
    """
    获取全局同步管理器实例

    Args:
        config: 配置参数

    Returns:
        同步管理器实例
    """
    global _global_sync_manager

    if _global_sync_manager is None:
        _global_sync_manager = DataSyncManager(config)

    return _global_sync_manager


# 便捷函数
async def create_stock_sync_task(symbols: list[str], schedule: str = "every_1h") -> str:
    """
    创建股票数据同步任务

    Args:
        symbols: 股票代码列表
        schedule: 调度表达式

    Returns:
        任务ID
    """
    sync_manager = get_sync_manager()

    task_id = f"stock_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task = SyncTask(
        id=task_id,
        name=f"股票数据同步 - {len(symbols)}只股票",
        sync_type=SyncType.SCHEDULED,
        data_source="realtime_data",
        parameters={"symbols": symbols},
        schedule=schedule,
    )

    success = sync_manager.add_task(task)
    return task_id if success else None


async def create_historical_sync_task(
    symbol: str, period: str = "1y", schedule: str = "daily_09:30"
) -> str:
    """
    创建历史数据同步任务

    Args:
        symbol: 股票代码
        period: 时间周期
        schedule: 调度表达式

    Returns:
        任务ID
    """
    sync_manager = get_sync_manager()

    task_id = f"historical_sync_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task = SyncTask(
        id=task_id,
        name=f"历史数据同步 - {symbol}",
        sync_type=SyncType.SCHEDULED,
        data_source="historical_data",
        parameters={"symbol": symbol, "period": period},
        schedule=schedule,
    )

    success = sync_manager.add_task(task)
    return task_id if success else None
