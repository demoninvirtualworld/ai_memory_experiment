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
            # L3: 要义记忆 - Verbatim → Gist 转化 + 情感显著性
            'gist_memory': {
                'description': '要义记忆（语义编码+情感显著性）',
                'theory': 'Fuzzy Trace Theory + Emotional Salience',
                'recent_turns': 3,  # 最近3轮保留原话
                'gist_max_chars': 500,  # 要义摘要最大字数
                # 情感显著性提取配置（参考CHI论文Table 2）
                'emotional_extraction': {
                    'enabled': True,
                    'extract_emotional_needs': True,   # 深层情感需求
                    'extract_core_values': True,       # 核心价值观
                    'extract_significant_events': True # 高情感强度事件
                }
            },
            # L4: 混合记忆 - 动态遗忘曲线（基于CHI'24 Hou et al.）
            'hybrid_memory': {
                'description': '混合记忆（动态遗忘曲线）',
                'theory': 'Ebbinghaus遗忘曲线 + Tulving陈述性记忆',
                'recent_turns': 3,  # 最近3轮（当前焦点）
                'retrieval_top_k': 5,  # 候选池扩大（阈值筛选后取top-k）
                # 动态遗忘曲线参数（CHI论文公式8-9）
                'forgetting_curve': {
                    'enabled': True,
                    'initial_g': 1.0,           # 初始固化系数 g_0
                    'recall_threshold': 0.86,   # 召回概率阈值（CHI论文建议值）
                    'time_unit': 'days',        # 时间单位
                    'update_on_recall': True    # 召回后更新固化系数
                }
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
        'model_provider': 'qwen',
        # 🔴 情感显著性配置（方案A+C混合）
        'emotional_salience': {
            # 方法选择: 'rule' (仅规则), 'llm' (纯LLM), 'hybrid' (混合，推荐)
            # 🔴 根据测试结果，直接使用LLM方法（准确率最高）
            'method': 'llm',
            # LLM调用阈值: 规则分数超过此值才调用LLM（仅hybrid模式有效）
            'llm_threshold': 0.2,
            # 是否启用LLM打分（可用于临时关闭，节省成本）
            'enable_llm': True,
            # LLM评分维度权重
            'weights': {
                'emotional_intensity': 0.4,      # 情感强度权重
                'self_disclosure_depth': 0.4,    # 自我披露深度权重
                'value_relevance': 0.2           # 价值观相关性权重
            }
        }
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
        # L4: 动态遗忘曲线参数（对应CHI论文公式）
        # alpha(时间敏感度)对应 e^{-t/g_n}, beta(语义相似度)对应 r, gamma(频率/固化强度)对应 g_n
        'hybrid_memory': {
            'alpha': 0.3,   # 时间衰减敏感度（融入遗忘曲线）
            'beta': 0.5,    # 语义相似度权重（对应论文中的 r）
            'gamma': 0.2,   # 频率/固化强度权重（对应论文中的 f/g_n）
        },
    }

    # 要义生成配置（L3 增强版：情感显著性提取）
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

        # L3 用户画像提取增强提示词（融合CHI论文的情感显著性）
        'profile_extraction_prompt': """你是一个用户画像分析助手。请根据以下对话，提取用户的长期特质。

**已知画像**：
{existing_profile}

**本次对话**（第 {task_id} 次任务）：
{conversation}

**任务**：
1. 提取本次对话中**新出现**的用户特质（不要重复已知画像）
2. **重要**：每个特质后面必须标注来源任务，格式为 "[Task N]"
3. 按以下分类整理：
   - basic_info: 基本信息（年龄、职业、身份等）
   - preferences: 偏好和喜好（饮食、爱好、品味等）
   - constraints: 限制和约束（过敏、时间限制、禁忌等）
   - goals: 目标和计划（近期目标、长期规划等）
   - personality: 性格特征（内向/外向、完美主义等）
   - social: 社交关系（家人、朋友、宠物等）

4. **🔴 情感显著性提取**（重要！这有助于AI展现更深层的"理解感"）：
   - emotional_needs: 用户表达的**深层情感需求**（如被理解、被认可、安全感、归属感等）
   - core_values: 用户透露的**核心价值观**（如家庭优先、事业导向、健康意识、自由追求等）
   - significant_events: **高情感强度事件**（如重大决定、人生转折、情绪波动时刻，标注情感类型：喜/怒/哀/惧/期待/失望等）

**输出格式示例**（纯 JSON，不要解释）：
{{
  "basic_info": {{"occupation": "博士生 [Task 1]"}},
  "preferences": ["喜欢爬山 [Task 1]", "素食主义者 [Task 1]"],
  "constraints": ["对海鲜过敏 [Task 1]"],
  "goals": ["准备考博 [Task 1]"],
  "personality": ["内向 [Task 1]"],
  "social": ["养了一只猫 [Task 1]"],
  "emotional_needs": ["希望被理解和认可 [Task 1]", "需要独处空间 [Task 1]"],
  "core_values": ["学术追求 [Task 1]", "健康生活 [Task 1]"],
  "significant_events": ["对未来职业方向感到迷茫（焦虑） [Task 1]"]
}}

如果本次对话没有新特质，返回空 JSON {{}}.
""",
    }