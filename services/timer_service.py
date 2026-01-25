"""
计时器服务 (Timer Service)

处理实验任务的计时逻辑：
- 900s 总时长管理
- 120s 空闲阈值判断（用户超过2分钟无操作，计时器暂停）
- 页面刷新/断网重连的恢复逻辑
- 与 DBManager 联动更新数据库

核心逻辑：
1. 用户每次发消息时调用 process_interaction_timer()
2. 如果距离上次交互 > 120s，不扣这段"空闲时间"
3. 如果 <= 120s，正常累计已用时间
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from database import DBManager, UserTask


@dataclass
class TimerState:
    """计时器状态"""
    started_at: Optional[datetime]
    total_duration: int  # 总时长（秒）
    elapsed_time: int  # 已用时间（秒）
    remaining_time: int  # 剩余时间（秒）
    is_expired: bool  # 是否已超时
    is_paused: bool  # 是否处于暂停状态（空闲超过120s）
    last_action_at: Optional[datetime]  # 最后交互时间

    def to_dict(self) -> Dict:
        return {
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'total_duration': self.total_duration,
            'elapsed_time': self.elapsed_time,
            'remaining_time': self.remaining_time,
            'is_expired': self.is_expired,
            'is_paused': self.is_paused,
            'last_action_at': self.last_action_at.isoformat() if self.last_action_at else None,
        }


class TimerService:
    """
    计时器服务

    处理实验任务的计时逻辑，支持：
    - 启动/停止计时器
    - 120s 空闲阈值判断
    - 页面刷新恢复
    """

    # 配置常量
    TOTAL_DURATION = 900  # 总时长 15分钟
    IDLE_THRESHOLD = 120  # 空闲阈值 2分钟

    def __init__(self, db_manager: DBManager):
        """
        初始化计时器服务

        Args:
            db_manager: 数据库管理器实例
        """
        self.db = db_manager

    def start_timer(self, user_id: str, task_id: int) -> TimerState:
        """
        启动任务计时器

        如果已启动，返回当前状态（支持页面刷新恢复）

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            TimerState: 计时器状态
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        # 如果已经启动过，返回当前状态
        if task.timer_started_at:
            return self._get_current_state(task, now)

        # 首次启动
        task.timer_started_at = now
        task.timer_total_duration = self.TOTAL_DURATION
        task.timer_elapsed_time = 0
        task.timer_is_expired = False
        task.timer_last_action_at = now

        self.db.session.commit()

        # 记录日志
        self.db.log_event(
            user_id=user_id,
            event_type='timer_start',
            task_id=task_id,
            event_data={'started_at': now.isoformat()}
        )

        return TimerState(
            started_at=now,
            total_duration=self.TOTAL_DURATION,
            elapsed_time=0,
            remaining_time=self.TOTAL_DURATION,
            is_expired=False,
            is_paused=False,
            last_action_at=now
        )

    def get_timer_state(self, user_id: str, task_id: int) -> TimerState:
        """
        获取计时器当前状态

        用于前端轮询/页面刷新恢复

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            TimerState: 计时器状态
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        return self._get_current_state(task, now)

    def process_interaction_timer(
        self,
        user_id: str,
        task_id: int
    ) -> Tuple[TimerState, bool]:
        """
        处理用户交互时的计时器更新

        核心逻辑：
        1. 计算距离上次交互的时间差
        2. 如果 > 120s（空闲阈值），不扣这段时间，只从当前时刻开始计时
        3. 如果 <= 120s，正常累计已用时间
        4. 更新 last_action_at 为当前时间

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            Tuple[TimerState, bool]: (计时器状态, 是否允许继续交互)
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        # 如果任务已提交或已超时，不允许继续
        if task.submitted or task.timer_is_expired:
            state = self._get_current_state(task, now)
            return state, False

        # 如果计时器未启动，先启动
        if not task.timer_started_at:
            state = self.start_timer(user_id, task_id)
            return state, True

        # 计算时间差
        last_action = task.timer_last_action_at or task.timer_started_at
        time_since_last_action = (now - last_action).total_seconds()

        # 判断是否超过空闲阈值
        if time_since_last_action > self.IDLE_THRESHOLD:
            # 超过 120s，不扣这段空闲时间
            # 只记录"恢复"事件，不增加 elapsed_time
            was_paused = True
            self.db.log_event(
                user_id=user_id,
                event_type='timer_resume',
                task_id=task_id,
                event_data={
                    'idle_duration': time_since_last_action,
                    'skipped': True,
                    'reason': f'idle > {self.IDLE_THRESHOLD}s'
                }
            )
        else:
            # 正常情况，累计已用时间
            was_paused = False
            task.timer_elapsed_time += int(time_since_last_action)

        # 更新最后交互时间
        task.timer_last_action_at = now

        # 检查是否超时
        if task.timer_elapsed_time >= task.timer_total_duration:
            task.timer_is_expired = True
            self.db.log_event(
                user_id=user_id,
                event_type='timer_expired',
                task_id=task_id,
                event_data={'elapsed_time': task.timer_elapsed_time}
            )

        self.db.session.commit()

        state = self._get_current_state(task, now)
        can_continue = not task.timer_is_expired

        return state, can_continue

    def update_elapsed_time(
        self,
        user_id: str,
        task_id: int,
        elapsed_time: int
    ) -> TimerState:
        """
        直接更新已用时间（前端同步用）

        注意：这个方法信任前端传来的 elapsed_time，
        但会进行合理性校验

        Args:
            user_id: 用户ID
            task_id: 任务ID
            elapsed_time: 前端报告的已用时间（秒）

        Returns:
            TimerState: 更新后的计时器状态
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        # 合理性校验：不允许时间倒退超过一定范围
        if elapsed_time < task.timer_elapsed_time - 10:
            # 时间倒退超过 10s，可能是异常，记录但不处理
            self.db.log_event(
                user_id=user_id,
                event_type='timer_anomaly',
                task_id=task_id,
                event_data={
                    'reported': elapsed_time,
                    'stored': task.timer_elapsed_time,
                    'action': 'ignored_regression'
                }
            )
        else:
            # 正常更新
            task.timer_elapsed_time = elapsed_time
            task.timer_last_action_at = now

            # 检查是否超时
            if elapsed_time >= task.timer_total_duration:
                task.timer_is_expired = True

            self.db.session.commit()

        return self._get_current_state(task, now)

    def check_can_interact(self, user_id: str, task_id: int) -> bool:
        """
        检查用户是否可以继续交互

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            bool: 是否允许继续交互
        """
        task = self.db.get_user_task(user_id, task_id)

        if not task:
            return True  # 任务不存在，允许创建

        if task.submitted:
            return False  # 已提交

        if task.timer_is_expired:
            return False  # 已超时

        if task.timer_elapsed_time >= task.timer_total_duration:
            return False  # 时间用完

        return True

    def force_expire(self, user_id: str, task_id: int) -> TimerState:
        """
        强制使计时器过期（管理员/调试用）

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            TimerState: 更新后的状态
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        task.timer_is_expired = True
        task.timer_elapsed_time = task.timer_total_duration

        self.db.session.commit()

        self.db.log_event(
            user_id=user_id,
            event_type='timer_force_expired',
            task_id=task_id
        )

        return self._get_current_state(task, now)

    def reset_timer(self, user_id: str, task_id: int) -> TimerState:
        """
        重置计时器（管理员/调试用）

        Args:
            user_id: 用户ID
            task_id: 任务ID

        Returns:
            TimerState: 重置后的状态
        """
        task = self.db.get_or_create_user_task(user_id, task_id)
        now = datetime.utcnow()

        task.timer_started_at = now
        task.timer_elapsed_time = 0
        task.timer_is_expired = False
        task.timer_last_action_at = now

        self.db.session.commit()

        self.db.log_event(
            user_id=user_id,
            event_type='timer_reset',
            task_id=task_id
        )

        return self._get_current_state(task, now)

    # ============ 私有方法 ============

    def _get_current_state(self, task: UserTask, now: datetime) -> TimerState:
        """
        计算当前计时器状态

        Args:
            task: 用户任务对象
            now: 当前时间

        Returns:
            TimerState: 计时器状态
        """
        if not task.timer_started_at:
            # 未启动
            return TimerState(
                started_at=None,
                total_duration=self.TOTAL_DURATION,
                elapsed_time=0,
                remaining_time=self.TOTAL_DURATION,
                is_expired=False,
                is_paused=False,
                last_action_at=None
            )

        elapsed = task.timer_elapsed_time
        total = task.timer_total_duration
        remaining = max(0, total - elapsed)
        is_expired = task.timer_is_expired or elapsed >= total

        # 判断是否处于暂停状态（距离上次交互超过 120s）
        is_paused = False
        if task.timer_last_action_at and not is_expired:
            idle_time = (now - task.timer_last_action_at).total_seconds()
            is_paused = idle_time > self.IDLE_THRESHOLD

        return TimerState(
            started_at=task.timer_started_at,
            total_duration=total,
            elapsed_time=elapsed,
            remaining_time=remaining,
            is_expired=is_expired,
            is_paused=is_paused,
            last_action_at=task.timer_last_action_at
        )

    def _calculate_active_time(
        self,
        task: UserTask,
        now: datetime
    ) -> int:
        """
        计算实际活跃时间（排除空闲时段）

        这是一个更复杂的实现，可以通过日志重建完整的时间线
        当前简化版本直接使用 elapsed_time

        Args:
            task: 用户任务对象
            now: 当前时间

        Returns:
            int: 活跃时间（秒）
        """
        # 简化实现：直接返回存储的 elapsed_time
        # 完整实现需要遍历日志重建时间线
        return task.timer_elapsed_time
