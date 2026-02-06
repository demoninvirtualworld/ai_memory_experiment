"""
SQLAlchemy 数据库模型定义

基于原有 JSON 数据结构设计，支持 150 人并发实验
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True)  # 登录用的唯一标识
    username = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)  # 显示名称
    age = Column(Integer)
    gender = Column(String(10))  # male, female, other

    # 实验相关
    memory_group = Column(String(20), nullable=False, default='sensory_memory')
    # 可选值: sensory_memory, working_memory, gist_memory, hybrid_memory

    user_type = Column(String(10), nullable=False, default='normal')  # normal, admin
    experiment_phase = Column(Integer, default=1)  # 当前实验阶段 1-4

    # 认证
    password_hash = Column(String(64), nullable=False)

    # 设置 (JSON 存储灵活配置)
    settings = Column(JSON, default=lambda: {
        'responseStyle': 'high',
        'aiAvatar': 'human'
    })

    # 人口统计学信息 (问卷用)
    demographics = Column(JSON, default=dict)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    tasks = relationship('UserTask', back_populates='user', cascade='all, delete-orphan')
    messages = relationship('ChatMessage', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User(user_id='{self.user_id}', name='{self.name}', memory_group='{self.memory_group}')>"


class UserTask(Base):
    """用户任务进度表"""
    __tablename__ = 'user_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, nullable=False)  # 任务编号 1-4

    # 任务状态
    submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)

    # 计时器
    timer_started_at = Column(DateTime, nullable=True)
    timer_total_duration = Column(Integer, default=900)  # 15分钟 = 900秒
    timer_elapsed_time = Column(Integer, default=0)  # 已消耗时间（秒）
    timer_is_expired = Column(Boolean, default=False)
    timer_last_action_at = Column(DateTime, nullable=True)  # 最后一次用户交互时间（用于120s阈值判断）

    # 文档
    document_title = Column(String(200), default='')
    document_content = Column(Text, default='')
    document_submitted = Column(Boolean, default=False)
    document_timestamp = Column(DateTime, nullable=True)

    # 问卷数据 (JSON 存储灵活性)
    questionnaire_data = Column(JSON, default=dict)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    user = relationship('User', back_populates='tasks')

    # 复合索引：快速查询用户的特定任务
    __table_args__ = (
        Index('idx_user_task', 'user_id', 'task_id', unique=True),
    )

    def __repr__(self):
        return f"<UserTask(user_id='{self.user_id}', task_id={self.task_id}, submitted={self.submitted})>"


class ChatMessage(Base):
    """聊天消息表

    设计考虑：
    1. 每条消息独立存储，便于检索和分析
    2. 添加 embedding_id 字段，预留给 Chroma 向量索引
    3. 支持按任务、按用户、按时间高效查询
    """
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), unique=True, nullable=False)  # 兼容原有格式 msg_xxx

    user_id = Column(String(50), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    task_id = Column(Integer, nullable=False)  # 任务编号 1-4

    content = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)  # True=用户消息, False=AI消息

    # L4 向量检索字段
    embedding = Column(Text, nullable=True)  # JSON 格式存储向量 [0.1, 0.2, ...]
    importance_score = Column(Float, default=0.5)  # 重要性分数 0-1

    # L4 动态遗忘曲线字段（基于CHI'24 Hou et al.）
    consolidation_g = Column(Float, default=1.0)      # 固化系数 g_n，越大衰减越慢
    recall_count = Column(Integer, default=0)          # 被召回次数 n
    last_recall_at = Column(DateTime, nullable=True)   # 上次被召回时间
    emotional_salience = Column(Float, default=0.0)    # 情感显著性分数 0-1

    # 元数据
    response_style = Column(String(10), nullable=True)  # high, low
    token_count = Column(Integer, nullable=True)  # 可选：记录 token 数

    # 时间戳
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # 关联
    user = relationship('User', back_populates='messages')

    # 索引优化：支持按用户+任务查询、按时间范围查询
    __table_args__ = (
        Index('idx_user_task_time', 'user_id', 'task_id', 'timestamp'),
    )

    def __repr__(self):
        role = "User" if self.is_user else "AI"
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<ChatMessage({role}: '{preview}')>"


class ExperimentLog(Base):
    """实验日志表

    记录关键实验事件，用于数据分析
    """
    __tablename__ = 'experiment_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)

    event_type = Column(String(50), nullable=False)
    # 事件类型: login, logout, task_start, task_submit, message_sent, timer_expired, etc.

    task_id = Column(Integer, nullable=True)

    # 事件详情 (JSON 灵活存储)
    event_data = Column(JSON, default=dict)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_user_event', 'user_id', 'event_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<ExperimentLog(user='{self.user_id}', event='{self.event_type}')>"


class UserProfile(Base):
    """用户画像表（L3 要义记忆专用）

    存储从对话中提取的长期特质，支持增量更新
    """
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)

    # 画像内容（JSON 格式）
    profile_data = Column(JSON, default=dict)
    # 格式示例（L3 增强版：含情感显著性）:
    # {
    #   "basic_info": {"age": 25, "occupation": "博士生"},
    #   "preferences": ["素食", "喜欢爬山", "养猫"],
    #   "constraints": ["对海鲜过敏", "工作日很忙"],
    #   "goals": ["准备考博", "学习Python"],
    #   "personality": ["内向", "完美主义"],
    #   "social": ["养了一只猫", "和室友住"],
    #   --- 情感显著性字段（CHI论文增强） ---
    #   "emotional_needs": ["希望被理解和认可", "需要独处空间"],
    #   "core_values": ["学术追求", "健康生活"],
    #   "significant_events": ["对未来职业方向感到迷茫（焦虑）"]
    # }

    # 最后更新的任务ID（用于增量更新）
    last_consolidated_task_id = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 索引
    __table_args__ = (
        Index('idx_user_profile', 'user_id', unique=True),
    )

    def __repr__(self):
        traits_count = sum(len(v) if isinstance(v, list) else 1 for v in (self.profile_data or {}).values())
        return f"<UserProfile(user='{self.user_id}', traits={traits_count})>"


# ============ 数据库初始化工具 ============

def init_db(db_path: str = 'data/experiment.db'):
    """
    初始化数据库

    Args:
        db_path: SQLite 数据库文件路径

    Returns:
        engine, SessionLocal
    """
    # SQLite 连接字符串
    # check_same_thread=False 允许多线程访问（Flask 需要）
    database_url = f"sqlite:///{db_path}?check_same_thread=False"

    engine = create_engine(
        database_url,
        echo=False,  # 生产环境关闭 SQL 日志
        pool_pre_ping=True,  # 连接健康检查
    )

    # 创建所有表
    Base.metadata.create_all(engine)

    # 创建会话工厂
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return engine, SessionLocal


def get_session(SessionLocal):
    """
    获取数据库会话（用于依赖注入）

    Usage:
        session = get_session(SessionLocal)
        try:
            # 数据库操作
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()
    """
    return SessionLocal()
