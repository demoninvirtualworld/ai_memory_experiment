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
        # 新的四级记忆架构（基于认知心理学理论）
        'memory_groups': ['sensory_memory', 'working_memory', 'gist_memory', 'hybrid_memory'],
        'memory_config': {
            # L1: 感觉记忆 - 无编码，仅当前输入
            'sensory_memory': {
                'description': '感觉记忆（控制组）',
                'theory': 'Atkinson-Shiffrin感觉寄存器',
                'capacity': 0,
                'turns': 0,
            },
            # L2: 工作记忆 - Miller 7±2 法则
            'working_memory': {
                'description': '工作记忆（7±2组块）',
                'theory': 'Miller 1956',
                'capacity': 7,  # 7轮对话
                'turns': 7,
            },
            # L3: 要义记忆 - Verbatim → Gist 转化
            'gist_memory': {
                'description': '要义记忆（语义编码）',
                'theory': 'Fuzzy Trace Theory',
                'recent_turns': 3,  # 最近3轮保留原话
                'gist_max_chars': 500,  # 要义摘要最大字数
            },
            # L4: 混合记忆 - 短时+长时检索
            'hybrid_memory': {
                'description': '混合记忆（联想检索）',
                'theory': 'Tulving陈述性记忆',
                'recent_turns': 3,  # 最近3轮（当前焦点）
                'retrieval_top_k': 3,  # 检索最相关的3条历史
            },
        },
        # 通义千问 API 配置
        'qwen_api_key': os.environ.get('QWEN_API_KEY', 'sk-2574182e8e0343d4a0fa1aaa181d42a8'),  # 需要设置环境变量或填入API Key
        'qwen_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'qwen_model': 'qwen-plus',  # 可选: qwen-turbo, qwen-plus, qwen-max
        'max_context_length': 128000,
        # DeepSeek 备用配置
        'deepseek_api_key': os.environ.get('DEEPSEEK_API_KEY', 'sk-98536e82c24d4ce59234f32c988eb597'),
        'deepseek_base_url': 'https://api.deepseek.com/v1',
        # 当前使用的模型提供商: 'qwen' 或 'deepseek'
        'model_provider': 'qwen'
    }

    # 对话配置
    DIALOGUE_CONFIG = {
        'max_history_messages': 10,  # 当前对话中保留的最大消息数
        'response_style_options': ['high', 'medium', 'low'],
        'default_response_style': 'high'
    }

    # 记忆操作配置
    MEMORY_OPERATIONS = {
        # 记忆读取权重 (α: 新鲜度, β: 相关性, γ: 重要性)
        'sensory_memory': {'alpha': 0, 'beta': 0, 'gamma': 0},   # 无读取
        'working_memory': {'alpha': 1, 'beta': 0, 'gamma': 0},   # 仅新鲜度
        'gist_memory': {'alpha': 0, 'beta': 0, 'gamma': 1},      # 仅重要性
        'hybrid_memory': {'alpha': 0.3, 'beta': 0.5, 'gamma': 0.2},  # 混合加权
    }

    # 要义生成配置
    GIST_CONFIG = {
        'summary_prompt_template': """请将以下对话历史压缩为{max_chars}字以内的要义摘要。

要求：
1. 保留核心语义和用户意图，去除具体措辞
2. 提取用户画像特征（性格、偏好、关注点）
3. 记录重要事件和情感状态
4. 使用第三人称描述

对话历史：
{conversation}

请输出要义摘要：""",
    }