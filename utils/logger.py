"""
实验日志工具 (Experiment Logger)

提供统一的日志格式化和输出：
- 控制台彩色输出
- 文件日志记录
- 结构化实验事件日志
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any


class ExperimentLogger:
    """
    实验日志记录器

    支持：
    - 控制台输出（带时间戳和级别）
    - 文件日志（按日期分割）
    - 结构化事件记录
    """

    def __init__(
        self,
        name: str = "experiment",
        log_dir: str = "logs",
        level: int = logging.INFO,
        console_output: bool = True,
        file_output: bool = True
    ):
        """
        初始化日志记录器

        Args:
            name: 日志记录器名称
            log_dir: 日志文件目录
            level: 日志级别
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
        """
        self.name = name
        self.log_dir = log_dir
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 避免重复添加 handler
        if not self.logger.handlers:
            # 日志格式
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # 控制台输出
            if console_output:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)

            # 文件输出
            if file_output:
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(
                    log_dir,
                    f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
                )
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def info(self, message: str):
        """记录 INFO 级别日志"""
        self.logger.info(message)

    def debug(self, message: str):
        """记录 DEBUG 级别日志"""
        self.logger.debug(message)

    def warning(self, message: str):
        """记录 WARNING 级别日志"""
        self.logger.warning(message)

    def error(self, message: str):
        """记录 ERROR 级别日志"""
        self.logger.error(message)

    def event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        task_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """
        记录结构化实验事件

        Args:
            event_type: 事件类型 (login, message, timer_start, etc.)
            user_id: 用户ID
            task_id: 任务ID
            data: 附加数据
        """
        parts = [f"[EVENT:{event_type}]"]

        if user_id:
            parts.append(f"user={user_id}")
        if task_id is not None:
            parts.append(f"task={task_id}")
        if data:
            # 简化数据输出，避免过长
            data_str = str(data)
            if len(data_str) > 200:
                data_str = data_str[:200] + "..."
            parts.append(f"data={data_str}")

        self.logger.info(" ".join(parts))

    def api_request(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        status: Optional[int] = None,
        duration_ms: Optional[float] = None
    ):
        """
        记录 API 请求日志

        Args:
            endpoint: API 端点
            method: HTTP 方法
            user_id: 用户ID
            status: 响应状态码
            duration_ms: 请求耗时(毫秒)
        """
        parts = [f"[API] {method} {endpoint}"]

        if user_id:
            parts.append(f"user={user_id}")
        if status:
            parts.append(f"status={status}")
        if duration_ms is not None:
            parts.append(f"duration={duration_ms:.1f}ms")

        self.logger.info(" ".join(parts))

    def llm_call(
        self,
        provider: str,
        model: str,
        user_id: Optional[str] = None,
        tokens: Optional[int] = None,
        duration_ms: Optional[float] = None,
        success: bool = True
    ):
        """
        记录 LLM 调用日志

        Args:
            provider: 提供商 (qwen, deepseek)
            model: 模型名称
            user_id: 用户ID
            tokens: token 数量
            duration_ms: 调用耗时
            success: 是否成功
        """
        status = "OK" if success else "FAIL"
        parts = [f"[LLM] {provider}/{model} [{status}]"]

        if user_id:
            parts.append(f"user={user_id}")
        if tokens:
            parts.append(f"tokens={tokens}")
        if duration_ms is not None:
            parts.append(f"duration={duration_ms:.1f}ms")

        if success:
            self.logger.info(" ".join(parts))
        else:
            self.logger.error(" ".join(parts))


# 全局默认实例
_default_logger: Optional[ExperimentLogger] = None


def get_logger(name: str = "experiment") -> ExperimentLogger:
    """
    获取日志记录器实例

    Args:
        name: 日志记录器名称

    Returns:
        ExperimentLogger 实例
    """
    global _default_logger

    if _default_logger is None or _default_logger.name != name:
        _default_logger = ExperimentLogger(name)

    return _default_logger
