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

### 2. 配置环境变量

```bash
# Windows PowerShell 示例
$env:SECRET_KEY="replace-with-a-random-secret"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_DB="ai_memory"
$env:POSTGRES_USER="ai_memory"
$env:POSTGRES_PASSWORD="replace-with-a-strong-password"
$env:QWEN_API_KEY="your-qwen-api-key"
```

- 通义千问: https://bailian.console.aliyun.com/

### 3. 数据库准备

```bash
python scripts/pre_launch_check.py
```

- 云端部署默认使用 Postgres，可通过 `DATABASE_URL` 或 `POSTGRES_*` 环境变量配置
- 首次启动时会自动建表
- 如果要把旧的 SQLite 数据迁移到 Postgres，使用 `python scripts/migrate_sqlite_to_postgres.py`

### 4. 启动服务

```bash
python app.py
```

访问地址: http://localhost:8000

### 5. 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | psy2025 |
| 被试 | 注册时创建 | 自定义 |

---

## Docker Compose 部署

### 1. 准备环境变量文件

```bash
copy .env.docker.example .env
```

填好 `.env` 中至少以下字段：`SECRET_KEY`、`POSTGRES_PASSWORD`、`QWEN_API_KEY`

### 2. 启动

```bash
docker compose up -d --build
```

访问地址：`http://localhost:8000`

---

## 五级记忆架构

### 总览

本实验设计五个记忆水平作为自变量，形成递阶的组间实验条件：

| 层级 | 标识 | 名称 | 理论基础 | 核心特点 |
|------|------|------|---------|---------|
| **L1** | `sensory_memory` | 感觉记忆 | Atkinson-Shiffrin (1968) | 完全无记忆（控制组） |
| **L2** | `working_memory` | 工作记忆 | Miller 7±2 (1956) | 近期7轮逐字记录 |
| **L3** | `gist_memory` | 要义记忆 | Fuzzy Trace Theory (1990) | LLM 语义画像 + 近3轮 |
| **L4** | `perfect_recall_memory` | 完全记忆 | Tulving (1972) 理想化版本 | 画像 + 纯语义 Top-K RAG |
| **L5** | `hybrid_memory` | 混合记忆 | Ebbinghaus + Tulving + CHI'24 | 画像 + RAG + 遗忘曲线 |

**核心对比设计：**
- L3 vs L4 → 隔离 RAG 的独立效应
- L4 vs L5 → 隔离遗忘曲线的独立效应

---

### L1: 感觉记忆 (Sensory Memory)

**理论基础：** Atkinson-Shiffrin 多重存储模型 (1968)，信息未进入意识加工即消失。

**数据流：**
```
当前输入 → AI 回复
```

**系统提示词：**
```
你没有任何关于用户的记忆，每次对话都是全新的开始，请不要假装记得。
```

**预期表现：** 无法理解跨轮次指代，话题完全断裂。

---

### L2: 工作记忆 (Working Memory)

**理论基础：** Miller (1956) 魔法数字 7±2，工作记忆容量有限，超出时发生位块替换。

**数据流：**
```
[最近 7 轮逐字记录] + 当前输入 → AI 回复
```

**系统提示词：**
```
你只能记住最近几轮的对话内容（约7轮），更早的内容已经消失。
```

**预期表现：** 第 8 轮开始遗忘第 1 轮内容。

---

### L3: 要义记忆 (Gist Memory)

**理论基础：** Fuzzy Trace Theory (Brainerd & Reyna, 1990)，语义要义比字面痕迹衰退更慢；融合 CHI'24 情感显著性提取。

**数据流：**
```
[LLM 用户画像（含情感显著性）] + [最近 3 轮原话] + 当前输入 → AI 回复
```

**固化机制：** Session 结束后，LLM 提取用户画像增量并写入 `user_profiles` 表。

**用户画像结构：**
```json
{
  "basic_info": {"occupation": "博士生 [Task 1]"},
  "preferences": ["喜欢爬山 [Task 1]"],
  "emotional_needs": ["希望被理解和认可 [Task 1]"],
  "core_values": ["学术追求 [Task 1]"],
  "significant_events": ["对未来职业方向感到迷茫（焦虑） [Task 1]"]
}
```

**系统提示词：**
```
你记得之前对话的大致内容和要点，了解用户的基本情况，
但不一定记得具体措辞——记得"聊过什么"但不记得"原话怎么说"。
```

**预期表现：** 理解用户的深层需求和价值观，但无法复现具体情节。

---

### L4: 完全记忆 (Perfect Recall Memory)

**理论基础：** Tulving (1972) 情节记忆的理想化版本——完整保留所有历史情节，无时间衰减。

**数据流：**
```
[LLM 用户画像] + [最近 3 轮原话] + [Top-K 语义相似度检索] + 当前输入 → AI 回复
```

**与 L3 的区别：** 在画像基础上，额外通过向量检索召回具体历史情节原文。

**与 L5 的区别：** 不使用遗忘曲线，所有历史消息的召回概率只取决于语义相似度，不随时间衰减。

**固化机制：** Session 结束后执行画像提取 + 向量 Embedding 生成（与 L5 相同）。

**检索方式：**
```python
# 纯余弦相似度 Top-K，alpha=0（无时间权重），beta=1（纯相似度）
vector_store.search_weighted(user_id, query, top_k=5, alpha=0.0, beta=1.0, gamma=0.0)
```

**预期表现：** 能精确引用用户在任意时间点说过的具体内容，不会遗忘任何细节。

---

### L5: 混合记忆 (Hybrid Memory)

**理论基础：** Tulving (1972) 陈述性记忆 + Ebbinghaus (1885) 遗忘曲线 + Hou et al. (CHI'24) 动态记忆召回模型。

**数据流：**
```
[LLM 用户画像] + [最近 3 轮原话] + [遗忘曲线过滤后的相关历史] + 当前输入 → AI 回复
```

**与 L4 的唯一区别：** 召回时施加遗忘曲线过滤，只有召回概率 p(t) ≥ 阈值的记忆才进入上下文。

#### 核心公式

**召回概率**（CHI'24 公式8）：

$$p_n(t) = \frac{1 - \exp(-r_{eff} \cdot e^{-t/g_n})}{1 - e^{-1}}$$

**情感调制相关度：**

$$r_{eff} = \min(1.0,\; r \times (1 + 0.3 \cdot e_{salience}))$$

**初始固化系数：**

$$g_0 = 3.0 + 1.5 \times e_{salience}$$

**固化系数更新（间隔效应）：**

$$g_n = g_{n-1} + S(t) \times (1 + 0.5 \cdot e_{salience}), \quad S(t) = \tanh\!\left(\frac{t}{2}\right)$$

| 符号 | 含义 |
|------|------|
| $r$ | 语义相似度（cosine similarity，0~1） |
| $e_{salience}$ | 情感显著性分数（LLM评估，0~1） |
| $t$ | 距上次召回的天数 |
| $g_n$ | 第 n 次召回后的固化系数 |

#### 情感显著性评估（LLM 三维打分）

| 维度 | 权重 | 高分示例 |
|------|------|---------|
| 情感强度 (Intensity) | 0.4 | "我真的崩溃了" |
| 自我披露深度 (Disclosure) | 0.4 | "我从没告诉过别人..." |
| 价值观相关性 (Value) | 0.2 | "家人是我最重要的事" |

#### 参数配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `initial_g` | 2.5 | 适配预实验较短间隔 |
| `recall_threshold` | 0.55 | 预实验降低阈值，便于观察 |
| `recent_turns` | 3 | 最近 3 轮当前焦点 |
| `retrieval_top_k` | 5 | 超阈值记忆取前 5 |

**预期表现：** 高情感记忆（如首次表达迷茫）在多周后依然被召回；普通记忆随时间衰减消失；用户感知"AI 像老朋友，记得我说过的重要的话"。

---

## 记忆架构对比

### 能力对比

| 能力维度 | L1 | L2 | L3 | L4 | L5 |
|---------|:--:|:--:|:--:|:---:|:--:|
| 近期对话记忆 | ✗ | ✓ | ✓ | ✓ | ✓ |
| LLM 用户画像 | ✗ | ✗ | ✓ | ✓ | ✓ |
| 情感显著性提取 | ✗ | ✗ | ✓ | ✓ | ✓ |
| 跨时间情节检索（RAG）| ✗ | ✗ | ✗ | ✓ | ✓ |
| 遗忘曲线过滤 | ✗ | ✗ | ✗ | ✗ | ✓ |
| 间隔效应强化 | ✗ | ✗ | ✗ | ✗ | ✓ |

### 数据流对比

```
L1:  当前输入 → AI回复

L2:  [最近7轮逐字] + 当前输入 → AI回复

L3:  [用户画像] + [最近3轮] + 当前输入 → AI回复

L4: [用户画像] + [最近3轮] + [Top-K语义检索] + 当前输入 → AI回复

L5:  [用户画像] + [最近3轮] + [遗忘曲线过滤后的检索] + 当前输入 → AI回复
```

### 固化机制对比

| 层级 | 固化时机 | 固化内容 | 存储位置 |
|------|---------|---------|---------|
| L1 | 无 | 无 | — |
| L2 | 无 | 无 | — |
| L3 | Session 结束后 | 用户画像（含情感显著性） | `user_profiles` 表 |
| L4 | Session 结束后 | 用户画像 + 向量 Embedding | `user_profiles` + `chat_messages` 表 |
| L5 | Session 结束后 | 用户画像 + 向量 + 固化系数 | `user_profiles` + `chat_messages` 表 |

---

## 实验流程

| 阶段 | 任务 | 目的 | 记忆操纵作用 |
|------|------|------|-------------|
| T1 | 关系建立与信息播种 | 收集用户信息 | 所有组条件相同 |
| T2 | 记忆触发测试 | 测试记忆能力 | **操纵首次生效** |
| T3 | 深度任务支持 | 个性化建议 | 记忆差异持续 |
| T4 | 综合评估与告别 | 回顾与告别 | 记忆差异影响告别体验 |

---

## 技术架构

### 项目结构

```
ai_memory_experiment/
├── app.py                    # Flask 主程序，API 路由，System Prompt 构建
├── config.py                 # 实验配置，记忆参数，提示词模板
├── requirements.txt          # Python 依赖
│
├── database/
│   ├── models.py             # SQLAlchemy 数据模型
│   ├── db_manager.py         # 数据库操作封装
│   └── vector_store.py       # 向量存储 + 遗忘曲线检索
│
├── services/
│   ├── memory_engine.py      # 五级记忆引擎（核心）
│   ├── consolidation_service.py  # 记忆固化服务（L3画像 / L4,L5向量）
│   ├── llm_service.py        # LLM 调用封装
│   └── timer_service.py      # 计时器服务
│
├── static/
│   ├── index.html            # 前端界面
│   └── questionnaire_config.js  # 问卷配置
│
├── scripts/
│   ├── migrate_add_dynamic_memory_fields.py  # 数据库迁移
│   └── manual_consolidation.py              # 手动触发固化
│
└── data/
    └── experiment.db         # 数据库（开发用，生产用 PostgreSQL）
```

### 核心类关系

```
┌──────────────────────────────────────────────────────────┐
│                        app.py                             │
│  接收消息 → 调用 MemoryEngine → 构建 Prompt → 调用 LLM   │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    MemoryEngine                           │
│  路由到 sensory / working / gist /                        │
│         perfect_recall / hybrid context                   │
└──────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────┐          ┌──────────────────────────┐
│   DBManager     │          │       VectorStore        │
│  消息/画像 CRUD  │          │  Embedding 生成          │
│  任务进度管理    │          │  Top-K 相似度检索（L4） │
└─────────────────┘          │  遗忘曲线检索（L5）      │
                             └──────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│               ConsolidationService                        │
│  L3: 提取用户画像（含情感显著性）                          │
│  L4/L5: 画像提取 + 批量向量 Embedding + 情感显著性分数   │
└──────────────────────────────────────────────────────────┘
```

---

## 理论参考

| 理论 | 作者 | 年份 | 应用层级 | 核心贡献 |
|------|------|------|---------|---------|
| 多重存储模型 | Atkinson & Shiffrin | 1968 | L1 | 感觉记忆 → 短时记忆 → 长时记忆 |
| 魔法数字 7±2 | Miller | 1956 | L2 | 工作记忆容量限制 |
| 模糊痕迹理论 | Brainerd & Reyna | 1990 | L3 | Verbatim vs. Gist 双痕迹 |
| 情景记忆 | Tulving | 1972 | L4 / L5 | 陈述性记忆，情节存储与提取 |
| 遗忘曲线 | Ebbinghaus | 1885 | L5 | 指数衰减，间隔效应 |
| 动态记忆召回 | Hou et al. (CHI'24) | 2024 | L5 | $p_n(t)$ 公式，固化系数更新 |

---

## License

MIT License
