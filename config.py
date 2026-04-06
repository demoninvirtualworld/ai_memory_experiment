import os
from pathlib import Path
from urllib.parse import quote_plus


BASE_DIR = Path(__file__).resolve().parent


def _load_local_env():
    """Load a local .env file without overriding real environment variables."""
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8-sig').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value


def _as_bool(value, default):
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _resolve_db_path(value):
    db_path = Path(value)
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    return db_path


def _build_sqlite_url():
    db_path = _resolve_db_path(os.environ.get('DB_PATH', 'data/experiment.db'))
    return f"sqlite:///{db_path.as_posix()}"


def _build_postgres_url():
    user = quote_plus(os.environ.get('POSTGRES_USER', 'ai_memory'))
    password = quote_plus(os.environ.get('POSTGRES_PASSWORD', 'ai_memory_password'))
    host = os.environ.get('POSTGRES_HOST') or os.environ.get('DB_HOST', '127.0.0.1')
    port = os.environ.get('POSTGRES_PORT', '5432')
    database = os.environ.get('POSTGRES_DB', 'ai_memory')
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def _build_database_url():
    explicit_url = os.environ.get('DATABASE_URL')
    if explicit_url:
        return explicit_url
    if _as_bool(os.environ.get('USE_SQLITE'), False):
        return _build_sqlite_url()
    return _build_postgres_url()


_load_local_env()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _build_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = _as_bool(os.environ.get('DEBUG'), True)
    PORT = int(os.environ.get('APP_PORT') or os.environ.get('PORT', 8000))
    HOST = os.environ.get('APP_HOST') or os.environ.get('HOST', '0.0.0.0') # Docker 内部运行必须用 0.0.0.0
    JSON_AS_ASCII = False
    SESSION_TTL_HOURS = int(os.environ.get('SESSION_TTL_HOURS', '168'))

    # 实验配置
    EXPERIMENT_CONFIG = {
        'countdown_time': 15 * 60,  # 15分钟对话时间
        'password': 'experiment123',  # 实验设置密码
        # 五级记忆架构（基于认知心理学理论）
        'memory_groups': ['sensory_memory', 'working_memory', 'gist_memory', 'perfect_recall_memory', 'hybrid_memory'],
        'memory_config': {
            # A: 感觉记忆 - 无编码，仅当前输入
            'sensory_memory': {
                'description': '感觉记忆（控制组）',
                'theory': 'Atkinson-Shiffrin感觉寄存器',
                'capacity': 0,
                'turns': 0,
            },
            # B: 工作记忆 - Miller 7±2 法则
            'working_memory': {
                'description': '工作记忆（7±2组块）',
                'theory': 'Miller 1956',
                'capacity': 7,  # 7轮对话
                'turns': 7,
            },
            # C: 要义记忆 - Verbatim → Gist 转化 + 情感显著性
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
            # D: 完全记忆 - 画像 + 纯语义相似度 Top-K RAG（无遗忘曲线）
            'perfect_recall_memory': {
                'description': '完全情节记忆（无衰减RAG）',
                'theory': 'Tulving陈述性记忆（理想化版本）',
                'recent_turns': 3,
                'retrieval_top_k': 5,  # 与 hybrid_memory 一致，保持公平对比
            },
            # E: 混合记忆 - 动态遗忘曲线（基于CHI'24 Hou et al.）
            'hybrid_memory': {
                'description': '混合记忆（动态遗忘曲线）',
                'theory': 'Ebbinghaus遗忘曲线 + Tulving陈述性记忆',
                'recent_turns': 3,  # 最近3轮（当前焦点）
                'retrieval_top_k': 5,  # 候选池扩大（阈值筛选后取top-k）
                # 动态遗忘曲线参数（CHI论文公式8-9）- 预实验调整
                'forgetting_curve': {
                    'enabled': True,
                    'initial_g': 2.5,           # 预实验：缩短间隔，增加召回
                    'recall_threshold': 0.55,   # 预实验：降低阈值，便于观察
                    'time_unit': 'days',        # 时间单位
                    'update_on_recall': True    # 召回后更新固化系数
                }
            },
        },
        # 通义千问 API 配置
        'qwen_api_key': os.environ.get('QWEN_API_KEY', ''),
        'qwen_base_url': os.environ.get('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
        'qwen_model': os.environ.get('QWEN_MODEL', 'qwen-plus'),
        'max_context_length': 128000,
        # DeepSeek 备用配置
        'deepseek_api_key': os.environ.get('DEEPSEEK_API_KEY', ''),
        'deepseek_base_url': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
        # 当前使用的模型提供商: 'qwen' 或 'deepseek'
        'model_provider': os.environ.get('MODEL_PROVIDER', 'qwen'),
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
        # D: 纯语义相似度（无时间衰减，无固化系数）
        'perfect_recall_memory': {'alpha': 0, 'beta': 1, 'gamma': 0},
        # E: 动态遗忘曲线参数（对应CHI论文公式）
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
