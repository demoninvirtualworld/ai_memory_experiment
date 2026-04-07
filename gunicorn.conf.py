#!/usr/bin/env python
"""
Gunicorn 配置文件 - 生产环境优化版

支持50并发请求配置：
- 使用gevent异步worker处理高并发
- 连接复用和资源优化
- 健康检查兼容
"""

import os
import multiprocessing

# 基础配置
bind = "0.0.0.0:8000"
workers = int(os.environ.get("WORKERS", 4))
worker_class = "gevent"
worker_connections = 1000  # 每个worker最大连接数
timeout = 120  # 请求超时时间（秒）
keepalive = 5  # keep-alive连接数
backlog = 2048  # 挂起连接队列大小

# 日志配置
accesslog = "-"  # 标准输出
errorlog = "-"  # 标准错误
loglevel = "info"

# 进程名称
proc_name = "ai_memory_experiment"

# 性能优化
max_requests = 1000  # 每个worker处理请求数后重启，防止内存泄漏
max_requests_jitter = 50  # 随机抖动，避免同时重启
graceful_timeout = 30  # 优雅关闭超时时间
limit_request_line = 8190  # 请求行最大长度
limit_request_fields = 100  # 请求头最大数量
limit_request_field_size = 8190  # 单个请求头最大大小

# 支持WebSocket（如果需要的话）
wsgi_app = "app:app"

# gevent特定配置
gevent_monkey = True  # 启用gevent monkey patch

# 环境变量
raw_env = [
    "PYTHONUNBUFFERED=1",
    "PYTHONDONTWRITEBYTECODE=1"
]

# 事件钩子
def on_starting(server):
    """服务器启动时调用"""
    server.log.info(f"AI记忆实验平台启动 - {workers} workers, {worker_class} worker class")

def post_worker_init(worker):
    """worker初始化后调用"""
    worker.log.info(f"Worker {worker.pid} 初始化完成")

def worker_exit(server, worker):
    """worker退出时调用"""
    server.log.info(f"Worker {worker.pid} 退出")

def on_exit(server):
    """服务器退出时调用"""
    server.log.info("AI记忆实验平台关闭")

# 打印配置信息
print(f"=== Gunicorn 配置 ===")
print(f"Workers: {workers}")
print(f"Worker Class: {worker_class}")
print(f"Worker Connections: {worker_connections}")
print(f"Bind: {bind}")
print(f"Timeout: {timeout}s")
print("====================")