"""
数据库管理器

封装所有 CRUD 操作，为 app.py 提供简洁的数据访问接口
"""

import hashlib
import secrets
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .models import User, UserTask, ChatMessage, ExperimentLog, UserProfile


class DBManager:
    """数据库管理器"""

    def __init__(self, session: Session):
        self.session = session

    # ============ 用户操作 ============

    def create_user(
        self,
        user_id: str,
        username: str,
        name: str,
        password: str,
        age: int = None,
        gender: str = None,
        memory_group: str = 'sensory_memory',
        user_type: str = 'normal'
    ) -> Optional[User]:
        """
        创建新用户

        Returns:
            User 对象，如果用户已存在则返回 None
        """
        # 检查用户是否已存在
        if self.get_user(user_id):
            return None

        user = User(
            user_id=user_id,
            username=username,
            name=name,
            age=age,
            gender=gender,
            memory_group=memory_group,
            user_type=user_type,
            password_hash=self._hash_password(password),
            settings={'responseStyle': 'high', 'aiAvatar': 'human'},
            demographics={},
            experiment_phase=1
        )

        try:
            self.session.add(user)
            self.session.commit()
            return user
        except IntegrityError:
            self.session.rollback()
            return None

    def get_user(self, user_id: str) -> Optional[User]:
        """根据 user_id 获取用户"""
        return self.session.query(User).filter(User.user_id == user_id).first()

    def get_all_users(self, user_type: str = None) -> List[User]:
        """获取所有用户，可按类型筛选"""
        query = self.session.query(User)
        if user_type:
            query = query.filter(User.user_type == user_type)
        return query.all()

    def verify_password(self, user_id: str, password: str) -> bool:
        """验证用户密码"""
        user = self.get_user(user_id)
        if not user:
            return False
        return user.password_hash == self._hash_password(password)

    def update_user_settings(self, user_id: str, settings: Dict) -> bool:
        """更新用户设置"""
        user = self.get_user(user_id)
        if not user:
            return False

        # 合并设置
        current_settings = user.settings or {}
        current_settings.update(settings)
        user.settings = current_settings
        self.session.commit()
        return True

    def update_user_phase(self, user_id: str, phase: int) -> bool:
        """更新用户实验阶段"""
        user = self.get_user(user_id)
        if not user:
            return False

        user.experiment_phase = min(4, max(1, phase))
        self.session.commit()
        return True

    def delete_user(self, user_id: str) -> bool:
        """删除用户（级联删除相关数据）"""
        user = self.get_user(user_id)
        if not user:
            return False

        self.session.delete(user)
        self.session.commit()
        return True

    # ============ 任务操作 ============

    def get_user_task(self, user_id: str, task_id: int) -> Optional[UserTask]:
        """获取用户的特定任务"""
        return self.session.query(UserTask).filter(
            UserTask.user_id == user_id,
            UserTask.task_id == task_id
        ).first()

    def get_or_create_user_task(self, user_id: str, task_id: int) -> UserTask:
        """获取或创建用户任务"""
        task = self.get_user_task(user_id, task_id)
        if task:
            return task

        # 创建新任务
        task = UserTask(
            user_id=user_id,
            task_id=task_id,
            timer_total_duration=900,  # 15分钟
            timer_elapsed_time=0,
            timer_is_expired=False
        )
        self.session.add(task)
        self.session.commit()
        return task

    def get_user_tasks(self, user_id: str) -> List[UserTask]:
        """获取用户所有任务"""
        return self.session.query(UserTask).filter(
            UserTask.user_id == user_id
        ).order_by(UserTask.task_id).all()

    def start_task_timer(self, user_id: str, task_id: int) -> Dict:
        """启动任务计时器"""
        task = self.get_or_create_user_task(user_id, task_id)

        # 如果已经启动过，返回现有状态
        if task.timer_started_at:
            remaining = max(0, task.timer_total_duration - task.timer_elapsed_time)
            return {
                'started_at': task.timer_started_at.isoformat(),
                'total_duration': task.timer_total_duration,
                'elapsed_time': task.timer_elapsed_time,
                'remaining_time': remaining,
                'is_expired': task.timer_is_expired
            }

        # 首次启动
        task.timer_started_at = datetime.utcnow()
        task.timer_elapsed_time = 0
        task.timer_is_expired = False
        self.session.commit()

        return {
            'started_at': task.timer_started_at.isoformat(),
            'total_duration': task.timer_total_duration,
            'elapsed_time': 0,
            'remaining_time': task.timer_total_duration,
            'is_expired': False
        }

    def update_task_timer(self, user_id: str, task_id: int, elapsed_time: int) -> Dict:
        """更新任务计时器"""
        task = self.get_or_create_user_task(user_id, task_id)

        task.timer_elapsed_time = elapsed_time
        if elapsed_time >= task.timer_total_duration:
            task.timer_is_expired = True

        self.session.commit()

        remaining = max(0, task.timer_total_duration - elapsed_time)
        return {
            'elapsed_time': elapsed_time,
            'remaining_time': remaining,
            'is_expired': task.timer_is_expired
        }

    def check_task_expired(self, user_id: str, task_id: int) -> bool:
        """检查任务是否超时"""
        task = self.get_user_task(user_id, task_id)
        if not task:
            return False
        return task.timer_is_expired or task.timer_elapsed_time >= task.timer_total_duration

    def submit_task(self, user_id: str, task_id: int, questionnaire_data: Dict = None) -> bool:
        """提交任务"""
        task = self.get_or_create_user_task(user_id, task_id)

        task.submitted = True
        task.submitted_at = datetime.utcnow()
        task.document_submitted = True

        if questionnaire_data:
            task.questionnaire_data = questionnaire_data

        # 更新用户实验阶段
        self.update_user_phase(user_id, task_id + 1)

        self.session.commit()
        return True

    def save_task_document(self, user_id: str, task_id: int, title: str, content: str) -> bool:
        """保存任务文档"""
        task = self.get_or_create_user_task(user_id, task_id)

        task.document_title = title
        task.document_content = content
        task.document_timestamp = datetime.utcnow()

        self.session.commit()
        return True

    # ============ 消息操作 ============

    def add_message(
        self,
        user_id: str,
        task_id: int,
        content: str,
        is_user: bool,
        response_style: str = None,
        embedding_id: str = None
    ) -> ChatMessage:
        """添加聊天消息"""
        message_id = f"msg_{datetime.utcnow().timestamp()}"

        message = ChatMessage(
            message_id=message_id,
            user_id=user_id,
            task_id=task_id,
            content=content,
            is_user=is_user,
            response_style=response_style,
            embedding_id=embedding_id,
            timestamp=datetime.utcnow()
        )

        self.session.add(message)
        self.session.commit()
        return message

    def get_task_messages(
        self,
        user_id: str,
        task_id: int,
        limit: int = None
    ) -> List[ChatMessage]:
        """获取任务的聊天消息"""
        query = self.session.query(ChatMessage).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.task_id == task_id
        ).order_by(ChatMessage.timestamp)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_user_all_messages(self, user_id: str) -> List[ChatMessage]:
        """获取用户所有消息（用于记忆上下文）"""
        return self.session.query(ChatMessage).filter(
            ChatMessage.user_id == user_id
        ).order_by(ChatMessage.task_id, ChatMessage.timestamp).all()

    def get_messages_before_task(self, user_id: str, task_id: int) -> List[ChatMessage]:
        """获取指定任务之前的所有消息（用于构建历史记忆）"""
        return self.session.query(ChatMessage).filter(
            ChatMessage.user_id == user_id,
            ChatMessage.task_id < task_id
        ).order_by(ChatMessage.task_id, ChatMessage.timestamp).all()

    def update_message_embedding(self, message_id: str, embedding_id: str) -> bool:
        """更新消息的向量 ID（Chroma 集成用）"""
        message = self.session.query(ChatMessage).filter(
            ChatMessage.message_id == message_id
        ).first()

        if not message:
            return False

        message.embedding_id = embedding_id
        self.session.commit()
        return True

    # ============ 日志操作 ============

    def log_event(
        self,
        user_id: str,
        event_type: str,
        task_id: int = None,
        event_data: Dict = None
    ) -> ExperimentLog:
        """记录实验事件"""
        log = ExperimentLog(
            user_id=user_id,
            event_type=event_type,
            task_id=task_id,
            event_data=event_data or {},
            timestamp=datetime.utcnow()
        )

        self.session.add(log)
        self.session.commit()
        return log

    def get_user_logs(
        self,
        user_id: str,
        event_type: str = None,
        limit: int = 100
    ) -> List[ExperimentLog]:
        """获取用户日志"""
        query = self.session.query(ExperimentLog).filter(
            ExperimentLog.user_id == user_id
        )

        if event_type:
            query = query.filter(ExperimentLog.event_type == event_type)

        return query.order_by(ExperimentLog.timestamp.desc()).limit(limit).all()

    # ============ 会话管理 ============

    @staticmethod
    def generate_session_token() -> str:
        """生成会话令牌"""
        return secrets.token_hex(32)

    @staticmethod
    def _hash_password(password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    # ============ 数据迁移工具 ============

    # 旧版本记忆组名称映射到新版本
    LEGACY_MEMORY_MAPPING = {
        'no_memory': 'sensory_memory',
        'short_memory': 'working_memory',
        'medium_memory': 'gist_memory',
        'long_memory': 'hybrid_memory',
    }

    def _normalize_memory_group(self, memory_group: str) -> str:
        """将旧版本记忆组名称转换为新版本"""
        return self.LEGACY_MEMORY_MAPPING.get(memory_group, memory_group)

    def import_from_json(self, user_data: Dict) -> Optional[User]:
        """
        从旧版 JSON 格式导入用户数据

        Args:
            user_data: 原有 JSON 格式的用户数据

        Returns:
            创建的 User 对象
        """
        # 转换旧版本记忆组名称
        memory_group = self._normalize_memory_group(
            user_data.get('memory_group', 'sensory_memory')
        )

        # 创建用户（跳过密码哈希，因为 JSON 里已经是哈希过的）
        user = User(
            user_id=user_data['user_id'],
            username=user_data.get('username', user_data['user_id']),
            name=user_data.get('name', ''),
            age=user_data.get('age'),
            gender=user_data.get('gender'),
            memory_group=memory_group,
            user_type=user_data.get('user_type', 'normal'),
            password_hash=user_data.get('password_hash', ''),
            settings=user_data.get('settings', {}),
            demographics=user_data.get('demographics', {}),
            experiment_phase=user_data.get('experiment_phase', 1),
            created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else datetime.utcnow()
        )

        try:
            self.session.add(user)
            self.session.flush()  # 获取 ID 但不提交

            # 导入任务数据
            for task_set in user_data.get('task_set', []):
                task = UserTask(
                    user_id=user.user_id,
                    task_id=task_set['task_id'],
                    submitted=task_set.get('submitted', False),
                    submitted_at=datetime.fromisoformat(task_set['submitted_at']) if task_set.get('submitted_at') else None,
                    timer_started_at=datetime.fromisoformat(task_set['timer']['started_at']) if task_set.get('timer', {}).get('started_at') else None,
                    timer_total_duration=task_set.get('timer', {}).get('total_duration', 900),
                    timer_elapsed_time=task_set.get('timer', {}).get('elapsed_time', 0),
                    timer_is_expired=task_set.get('timer', {}).get('is_expired', False),
                    document_title=task_set.get('document', {}).get('title', ''),
                    document_content=task_set.get('document', {}).get('content', ''),
                    document_submitted=task_set.get('document', {}).get('submitted', False),
                    questionnaire_data=task_set.get('questionnaire', {})
                )
                self.session.add(task)

                # 导入对话消息
                for msg in task_set.get('conversation', []):
                    message = ChatMessage(
                        message_id=msg.get('message_id', f"msg_{datetime.utcnow().timestamp()}"),
                        user_id=user.user_id,
                        task_id=task_set['task_id'],
                        content=msg['content'],
                        is_user=msg.get('is_user', True),
                        timestamp=datetime.fromisoformat(msg['timestamp']) if msg.get('timestamp') else datetime.utcnow()
                    )
                    self.session.add(message)

            self.session.commit()
            return user

        except Exception as e:
            self.session.rollback()
            raise e

    # ============ 统计接口 ============

    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        user = self.get_user(user_id)
        if not user:
            return {}

        tasks = self.get_user_tasks(user_id)
        completed_tasks = sum(1 for t in tasks if t.submitted)

        total_messages = self.session.query(ChatMessage).filter(
            ChatMessage.user_id == user_id
        ).count()

        return {
            'user_id': user_id,
            'name': user.name,
            'memory_group': user.memory_group,
            'experiment_phase': user.experiment_phase,
            'completed_tasks': completed_tasks,
            'total_tasks': 4,
            'total_messages': total_messages,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }

    # ============ 用户画像操作（L3 要义记忆专用） ============

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户画像

        Args:
            user_id: 用户ID

        Returns:
            画像数据（Dict），如果不存在则返回空画像
        """
        profile = self.session.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()

        if profile:
            return profile.profile_data or {}

        # 返回默认空画像
        return {
            "basic_info": {},
            "preferences": [],
            "constraints": [],
            "goals": [],
            "personality": [],
            "social": []
        }

    def save_user_profile(
        self,
        user_id: str,
        profile_data: Dict[str, Any],
        last_task_id: int = None
    ) -> bool:
        """
        保存或更新用户画像

        Args:
            user_id: 用户ID
            profile_data: 画像数据
            last_task_id: 最后更新的任务ID

        Returns:
            是否成功
        """
        try:
            profile = self.session.query(UserProfile).filter(
                UserProfile.user_id == user_id
            ).first()

            if profile:
                # 更新现有画像
                profile.profile_data = profile_data
                profile.updated_at = datetime.utcnow()
                if last_task_id is not None:
                    profile.last_consolidated_task_id = last_task_id
            else:
                # 创建新画像
                profile = UserProfile(
                    user_id=user_id,
                    profile_data=profile_data,
                    last_consolidated_task_id=last_task_id or 0
                )
                self.session.add(profile)

            self.session.commit()
            return True

        except Exception as e:
            print(f"[DBManager] 保存用户画像失败: {e}")
            self.session.rollback()
            return False

    def get_profile_last_consolidated_task(self, user_id: str) -> int:
        """
        获取用户画像最后一次固化的任务ID

        Args:
            user_id: 用户ID

        Returns:
            任务ID，如果从未固化则返回 0
        """
        profile = self.session.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()

        return profile.last_consolidated_task_id if profile else 0
