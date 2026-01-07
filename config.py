import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ai-memory-experiment-secret-key'
    DEBUG = True
    JSON_AS_ASCII = False

    # 实验配置
    EXPERIMENT_CONFIG = {
        'countdown_time': 15 * 60,  # 15分钟对话时间
        'password': 'experiment123',  # 实验设置密码
        'memory_groups': ['no_memory', 'short_memory', 'medium_memory', 'long_memory'],
        'memory_tokens': {
            'no_memory': 0,
            'short_memory': 2000,
            'medium_memory': 8000,
            'long_memory': 128000  # 128k tokens
        },
        'deepseek_api_key': os.environ.get('DEEPSEEK_API_KEY', 'sk-98536e82c24d4ce59234f32c988eb597'),
        'deepseek_base_url': 'https://api.deepseek.com/v1',
        'max_context_length': 128000  # DeepSeek支持128k上下文
    }

    # 对话配置
    DIALOGUE_CONFIG = {
        'max_history_messages': 10,  # 当前对话中保留的最大消息数
        'response_style_options': ['high', 'medium', 'low'],
        'default_response_style': 'high'
    }

    # 记忆配置
    MEMORY_CONFIG = {
        'short_memory_ratio': 0.33,  # 短记忆组使用最近对话的1/3
        'medium_memory_summary_max_tokens': 2000,  # 中记忆组摘要最大token数
        'enable_adaptive_memory': True  # 是否启用自适应记忆
    }