# AI 记忆能力实验平台

基于认知心理学理论，研究大模型不同记忆架构对人机交互质量的影响。

## 研究背景

人类记忆遵循从感觉记忆到短时记忆再到长时记忆的渐进过程。本实验将认知心理学的记忆理论系统性地应用于 AI 对话系统，探究不同记忆架构如何影响用户对人机关系的感知。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

编辑 `config.py`，填入 API Key：

```python
'qwen_api_key': 'your-api-key-here',      # 通义千问
'deepseek_api_key': 'your-api-key-here',  # DeepSeek (备用)
```

- 通义千问: https://bailian.console.aliyun.com/
- DeepSeek: https://platform.deepseek.com/

### 3. 启动服务

```bash
python app.py
```

访问地址: http://localhost:8000

### 4. 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | psy2025 |
| 被试 | 注册时创建 | 自定义 |

---

## 实验设计

### 自变量：四级记忆架构

基于认知心理学理论，设计了四个记忆水平：

| 层级 | 名称 | 理论基础 | 实现方式 | 读取公式 |
|------|------|---------|---------|---------|
| **L1** | 感觉记忆 | Atkinson-Shiffrin 感觉寄存器 | 无历史记忆，仅当前输入 | 无 |
| **L2** | 工作记忆 | Miller (1956) 7±2 法则 | 保留最近 **7 轮**对话 | α=1 (仅新鲜度) |
| **L3** | 要义记忆 | Fuzzy Trace Theory | 最近 3 轮原话 + 历史**要义摘要** | γ=1 (仅重要性) |
| **L4** | 混合记忆 | Tulving 陈述性记忆 | 最近 3 轮 + **相关性检索** Top-3 | α,β,γ 混合 |

### 核心机制详解

#### L1: 感觉记忆 (Sensory Memory)
```
外界刺激 → [感觉寄存器] → 消失（未编码）
```
- **心理学**: 信息仅在感觉寄存器停留约 250ms，未进入意识加工
- **AI 实现**: 每轮对话清空历史，只有当前消息
- **预期表现**: 无法理解指代（如"它"指什么），话题完全断裂

#### L2: 工作记忆 (Working Memory)
```
信息流入 → [7±2 组块缓冲区] → 溢出时旧项被替换
```
- **心理学**: Miller 的魔法数字，以组块(Chunk)为单位存储
- **AI 实现**: 保留最近 7 轮对话（约 14 条消息）
- **预期表现**: 记得近期内容，但第 8 轮开始遗忘第 1 轮

#### L3: 要义记忆 (Gist Memory)
```
原始输入 → [编码] → Verbatim(字面,衰退快) + Gist(要义,衰退慢)
```
- **心理学**: Fuzzy Trace Theory，语义编码产生要义痕迹
- **AI 实现**: 最近 3 轮保留原话，更早历史压缩为 500 字要义摘要
- **预期表现**: 记得"聊过什么"但不记得"原话怎么说"

#### L4: 混合记忆 (Hybrid Memory)
```
当前查询 → [短时焦点 + 长时检索] → 相关记忆被唤醒
```
- **心理学**: 陈述性记忆的提取依赖性，扩散激活
- **AI 实现**: 最近 3 轮 + 基于相关性检索的 3 条历史片段
- **预期表现**: 跨时空回忆，提到某话题时能想起相关历史

### 实验流程

| 阶段 | 任务 | 目的 |
|------|------|------|
| 第 1 次 | 关系建立与信息播种 | 收集用户信息，建立信任基础 |
| 第 2 次 | 记忆触发测试 | 测试 AI 对历史信息的回忆能力 |
| 第 3 次 | 深度任务支持 | 基于记忆提供个性化建议 |
| 第 4 次 | 综合评估与告别 | 回顾关系发展，告别体验 |

### 因变量（建议测量）

```
├── 认知层面
│   ├── 感知记忆能力 ("AI 记得多少")
│   ├── 感知理解度 ("AI 理解我")
│   └── 交互流畅度
├── 情感层面
│   ├── 关系亲密度
│   ├── 信任度
│   └── 满意度
├── 行为层面
│   ├── 持续使用意愿
│   └── 自我披露程度
└── 负面感知
    ├── 隐私担忧
    └── 恐怖谷效应
```

---

## 技术架构

### 项目结构

```
ai_memory_experiment/
├── app.py              # Flask 主程序，API 路由
├── config.py           # 实验配置，记忆参数
├── models.py           # MemoryContext 类（四级记忆实现）
├── utils.py            # LLM 管理器，摘要生成
├── requirements.txt    # Python 依赖
├── static/
│   └── index.html      # 前端界面
└── data/
    └── users/          # 用户数据 (JSON)
```

### 核心类

#### MemoryContext (models.py)

```python
class MemoryContext:
    WORKING_MEMORY_TURNS = 7   # Miller's 7±2
    RECENT_VERBATIM_TURNS = 3  # 保留原话的轮数
    RETRIEVAL_TOP_K = 3        # 检索的历史片段数
    GIST_MAX_CHARS = 500       # 要义摘要最大字数

    def get_context_for_task(self, task_id):
        # 根据 memory_group 返回不同的记忆上下文
        ...
```

#### 记忆读取公式

$$m^* = \arg\min_{m \in M} (\alpha \cdot s_{rec} + \beta \cdot s_{rel} + \gamma \cdot s_{imp})$$

- $s_{rec}$: 新鲜度分数 (Recency)
- $s_{rel}$: 相关性分数 (Relevance)
- $s_{imp}$: 重要性分数 (Importance)

### 配置说明 (config.py)

```python
EXPERIMENT_CONFIG = {
    'memory_groups': ['sensory_memory', 'working_memory', 'gist_memory', 'hybrid_memory'],
    'memory_config': {
        'sensory_memory': {'turns': 0},
        'working_memory': {'turns': 7},
        'gist_memory': {'recent_turns': 3, 'gist_max_chars': 500},
        'hybrid_memory': {'recent_turns': 3, 'retrieval_top_k': 3},
    }
}

MEMORY_OPERATIONS = {
    'sensory_memory': {'alpha': 0, 'beta': 0, 'gamma': 0},
    'working_memory': {'alpha': 1, 'beta': 0, 'gamma': 0},
    'gist_memory': {'alpha': 0, 'beta': 0, 'gamma': 1},
    'hybrid_memory': {'alpha': 0.3, 'beta': 0.5, 'gamma': 0.2},
}
```

---

## API 接口

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/logout` | 用户登出 |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ai/response` | 获取 AI 回复 |
| GET | `/api/users/me/tasks/{id}/chats` | 获取聊天记录 |

### 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users` | 获取所有用户 |
| GET | `/api/admin/users/{id}` | 获取用户详情 |

---

## 常见问题

### Q: 如何切换 LLM 提供商？

修改 `config.py`:
```python
'model_provider': 'qwen'     # 通义千问
'model_provider': 'deepseek' # DeepSeek
```

### Q: 如何重置实验数据？

```bash
# 方法 1: 删除用户文件
rm -rf data/users/*.json

# 方法 2: API 调用
curl -X POST http://localhost:8000/api/debug/reset
```

### Q: 旧版本用户数据兼容吗？

是的，系统会自动将旧版记忆组名称映射到新名称：
- `no_memory` → `sensory_memory`
- `short_memory` → `working_memory`
- `medium_memory` → `gist_memory`
- `long_memory` → `hybrid_memory`

### Q: L4 混合记忆的向量检索如何实现？

当前为简化版（基于关键词匹配）。生产环境建议：
1. 使用 `text-embedding-3-small` 生成向量
2. 存储到向量数据库（ChromaDB / FAISS）
3. 基于余弦相似度检索

---

## 理论参考

| 理论 | 作者 | 年份 | 应用层级 |
|------|------|------|---------|
| 多重存储模型 | Atkinson & Shiffrin | 1968 | L1 |
| 魔法数字 7±2 | Miller | 1956 | L2 |
| 模糊痕迹理论 | Brainerd & Reyna | 1990 | L3 |
| 情景记忆 | Tulving | 1972 | L4 |

---

## License

MIT License
