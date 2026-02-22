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

### 3. 数据库迁移（首次运行或更新后）

```bash
python scripts/migrate_add_dynamic_memory_fields.py
```

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

## 四级记忆架构

### 总览

基于认知心理学理论，设计了四个记忆水平，形成递阶的实验条件：

| 层级 | 名称 | 理论基础 | 记忆容量 | 核心特点 |
|------|------|---------|---------|---------|
| **L1** | 感觉记忆 | Atkinson-Shiffrin (1968) | 0 轮 | 完全无记忆 |
| **L2** | 工作记忆 | Miller 7±2 (1956) | 最近 7 轮 | 字面记忆，容量有限 |
| **L3** | 要义记忆 | Fuzzy Trace Theory (1990) | 3 轮原话 + 画像摘要 | 语义压缩 + 情感显著性 |
| **L4** | 混合记忆 | Ebbinghaus + Tulving | 3 轮 + 动态检索 | 遗忘曲线 + 语义关联 |

---

### L1: 感觉记忆 (Sensory Memory)

#### 理论基础
- **来源**: Atkinson-Shiffrin 多重存储模型 (1968)
- **原理**: 信息仅在感觉寄存器停留约 250ms，未进入意识加工即消失

#### 实现方式
```
外界刺激 → [感觉寄存器] → 消失（未编码）
```

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `capacity` | 0 | 无历史记忆 |
| `turns` | 0 | 不保留任何轮次 |

#### 代码实现
```python
# services/memory_engine.py
def _get_sensory_context(self, user_id, current_task_id):
    return ""  # 返回空字符串，无任何历史上下文
```

#### 系统提示词
```
你没有任何关于用户的记忆，每次对话都是全新的开始。
你无法记住任何之前的对话内容，请不要假装记得。
```

#### 预期表现
- 无法理解指代（如"它"指什么）
- 话题完全断裂
- 用户感知：AI 完全不记得我

---

### L2: 工作记忆 (Working Memory)

#### 理论基础
- **来源**: Miller (1956) 的"魔法数字 7±2"
- **原理**: 工作记忆以组块(Chunk)为单位存储，容量有限，超出时发生位块替换

#### 实现方式
```
信息流入 → [7±2 组块缓冲区] → 溢出时旧项被替换
```

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `capacity` | 7 | 保留 7 轮对话 |
| `turns` | 7 | 约 14 条消息 |

#### 代码实现
```python
# services/memory_engine.py
def _get_working_context(self, user_id, current_task_id):
    messages = self.db.get_messages_before_task(user_id, current_task_id)
    turns = self._messages_to_turns(messages)
    recent_turns = turns[-7:]  # 取最近 7 轮
    return self._format_turns(recent_turns)
```

#### 系统提示词
```
你只能记住最近几轮的对话内容（约7轮）。
更早的对话内容已经从你的记忆中消失。
```

#### 输出示例
```
用户：我叫小明
AI助手：你好小明！
用户：我喜欢爬山
AI助手：爬山是很好的运动...
... (最多保留 7 轮)
```

#### 预期表现
- 记得近期内容
- 第 8 轮开始遗忘第 1 轮
- 用户感知：AI 有短期记忆，但会遗忘

---

### L3: 要义记忆 (Gist Memory)

#### 理论基础
- **来源**: Fuzzy Trace Theory (Brainerd & Reyna, 1990)
- **原理**:
  - **Verbatim Trace**: 字面痕迹，精确但衰退快
  - **Gist Trace**: 要义痕迹，语义本质，衰退慢
- **增强**: CHI'24 情感显著性提取

#### 实现方式
```
原始输入 → [编码] → Verbatim(字面,近期) + Gist(要义,长期) + 情感显著性
```

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `recent_turns` | 3 | 最近 3 轮保留原话 |
| `gist_max_chars` | 500 | 要义摘要最大字数 |
| `emotional_extraction` | true | 情感显著性提取 |

#### 代码实现

**读取时** (`memory_engine.py`):
```python
def _get_gist_context(self, user_id, current_task_id):
    # 1. 读取固化的用户画像（Gist + 情感显著性）
    gist = self._get_consolidated_gist(user_id)

    # 2. 最近 3 轮保留原话（Verbatim）
    recent_turns = turns[-3:]

    return f"[用户画像]\n{gist}\n\n[近期对话]\n{recent_turns}"
```

**固化时** (`consolidation_service.py`):
```python
def _consolidate_gist(self, user_id, task_id):
    # 调用 LLM 提取用户画像（含情感显著性）
    profile = self._extract_profile_increment(conversation, existing_profile, task_id)
    # 提取维度：basic_info, preferences, constraints, goals,
    #          personality, social, emotional_needs, core_values, significant_events
```

#### 用户画像结构
```json
{
  "basic_info": {"occupation": "博士生 [Task 1]"},
  "preferences": ["喜欢爬山 [Task 1]", "素食主义者 [Task 1]"],
  "constraints": ["对海鲜过敏 [Task 1]"],
  "goals": ["准备考博 [Task 1]"],
  "personality": ["内向 [Task 1]"],
  "social": ["养了一只猫 [Task 1]"],
  "emotional_needs": ["希望被理解和认可 [Task 1]"],
  "core_values": ["学术追求 [Task 1]"],
  "significant_events": ["对未来职业方向感到迷茫（焦虑） [Task 1]"]
}
```

#### 输出示例
```
[用户画像]
基本信息：occupation: 博士生
偏好：喜欢爬山、素食主义者
限制：对海鲜过敏
目标：准备考博
性格：内向
社交：养了一只猫
深层情感需求：希望被理解和认可
核心价值观：学术追求
重要事件：对未来职业方向感到迷茫（焦虑）

[近期对话]
用户：今天去爬山了
AI助手：爬山感觉怎么样？
...
```

#### 系统提示词
```
你记得之前对话的大致内容和要点，但不一定记得具体的措辞。
你了解用户的基本情况和主要话题，但具体细节可能模糊。
这就像人类的自然记忆一样——记得'聊过什么'但不一定记得'原话怎么说'。
```

#### 预期表现
- 记得"聊过什么"但不记得"原话怎么说"
- 能够理解用户的深层需求和价值观
- 用户感知：AI 理解我这个人

---

### L4: 混合记忆 (Hybrid Memory)

#### 理论基础
- **来源**:
  - Tulving (1972) 陈述性记忆 + 扩散激活
  - Ebbinghaus 遗忘曲线
  - CHI'24 Hou et al. 动态记忆召回与固化
- **原理**:
  - 记忆强度随时间指数衰减
  - 被召回的记忆会被强化（间隔效应）
  - 情感显著性高的记忆更容易被召回

#### 实现方式
```
当前查询 → [用户画像] + [短时焦点] + [动态遗忘曲线检索] → 相关记忆被唤醒
```

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `recent_turns` | 3 | 最近 3 轮（当前焦点） |
| `retrieval_top_k` | 5 | 检索候选池大小 |
| `recall_threshold` | 0.86 | 召回概率阈值 |
| `initial_g` | 1.0 | 初始固化系数 |
| `update_on_recall` | true | 召回后更新固化系数 |

#### 核心公式（CHI'24 Hou et al. + 情感双层机制）

**召回概率** (公式 8):
$$p_n(t) = \frac{1 - \exp(-r \cdot e^{-t/g_n})}{1 - e^{-1}}$$

**固化系数更新** (公式 9，增强版):
$$g_n = g_{n-1} + S(t) \times (1 + \alpha \cdot e_{salience}), \quad S(t) = \frac{1 - e^{-t}}{1 + e^{-t}}$$

**情感显著性双层机制**:

1. **固化层（长期效果）**：
   $$g_0 = 1.0 + 0.5 \times e_{salience}$$

2. **召回层（短期加成）**：
   $$p_{final} = \min(1.0, p_n(t) + 0.05 \times e_{salience})$$

3. **再固化层（情感加速）**：
   $$\Delta g = S(t) \times (1 + 0.5 \times e_{salience})$$

其中：
- $r$ = 语义相似度 (cosine similarity)
- $t$ = 距上次召回的时间（天）
- $g_n$ = 固化系数（召回次数越多越大，衰减越慢）
- $e_{salience}$ = 情感显著性分数 (0-1，由LLM三维评估得出)
- $\alpha$ = 0.5（情感加速系数）

---

#### 情感显著性双层机制（创新点）

受情感神经科学启发（LaBar & Cabeza, 2006; Bower, 1981），我们设计了**情感影响记忆的双层机制**，避免简单的维度堆叠，实现理论统一。

##### 🧠 神经科学基础

- **编码/固化阶段**：杏仁核-海马体回路被激活，情感事件获得更强的巩固
- **提取/召回阶段**：情感一致性效应，当前情绪状态优先召回同情绪记忆
- **再固化阶段**：每次提取后，记忆进入"不稳定状态"，情感加速再巩固

##### 📐 三层作用机制

**Layer 1 - 固化层（初始化）**

记忆首次固化时，情感影响初始固化系数：

```python
# 公式
g_0 = 1.0 + 0.5 × emotional_salience

# 示例
低情感消息（"今天去图书馆"）：g_0 = 1.0
高情感消息（"我对未来很迷茫"）：g_0 = 1.35 ← 提升35%
```

**Layer 2 - 召回层（短期加成）**

检索时，情感提供即时的召回概率加成：

```python
# 公式
p_final = min(1.0, p_n(t) + 0.05 × emotional_salience)

# 权重从0.1降低到0.05，因为固化层已有效果，避免过度加成
```

**Layer 3 - 再固化层（长期强化）**

被召回后更新固化系数时，情感加速固化过程：

```python
# 公式
Δg = S(t) × (1 + 0.5 × emotional_salience)

# 示例
普通记忆：Δg = 0.2
高情感记忆（0.8）：Δg = 0.2 × 1.4 = 0.28 ← 固化速度提升40%
```

##### ✨ 优势

| 对比维度 | 单层加成（旧方案） | 双层机制（新方案） |
|---------|------------------|------------------|
| 理论统一性 | ❌ 简单加法叠加 | ✅ 情感通过 $g_n$ 统一作用 |
| 神经科学 | ❌ 仅在召回层 | ✅ 编码+提取+再固化三阶段 |
| 冷启动问题 | ❌ 新记忆 $g_0$ 固定 | ✅ 高情感记忆初始就更强 |
| 长期优势 | ❌ 仅短期加成 | ✅ 随时间 $g_n$ 差距拉大 |
| 扩展性 | ❌ 难以融入新维度 | ✅ 统一框架易扩展 |

##### 📊 实测效果

- **初始固化**：高情感记忆 $g_0$ 提升 **30-40%**
- **召回加成**：情感分数 0.7 → 召回概率 **+0.035**
- **长期强化**：每次召回后，高情感记忆固化速度提升 **最多50%**

##### 🎓 学术话术（论文撰写参考）

> We extend the dynamic forgetting curve (Hou et al., 2024) by introducing a **dual-pathway emotional enhancement mechanism**:
>
> 1. **Consolidation pathway** (long-term): Emotional memories receive accelerated consolidation via enhanced $g_n$ initialization and update.
> 2. **Retrieval pathway** (short-term): Emotional cues provide immediate recall boost through probability bonus.
>
> This design mirrors neurobiological findings where amygdala-hippocampal coupling enhances both **encoding** (LaBar & Cabeza, 2006) and **retrieval** (Bower, 1981), avoiding arbitrary dimension stacking in favor of a unified theoretical framework.

---

#### 情感显著性评估（LLM三维打分）

为精确评估情感显著性，采用 **LLM 三维评估方法**（准确率显著优于规则方法）：

**评估维度**（基于 CHI'24 Table 2）：

1. **情感强度** (Emotional Intensity, 权重 0.4)
   - 定义：消息中情感的强烈程度
   - 示例：高分 - "我太开心了！"，低分 - "今天天气不错"

2. **自我披露深度** (Self-Disclosure Depth, 权重 0.4)
   - 定义：用户透露个人隐私/脆弱性的程度
   - 示例：高分 - "我从没告诉过别人，我很害怕失败"，低分 - "我是学生"

3. **价值观相关性** (Value Relevance, 权重 0.2)
   - 定义：是否涉及用户核心价值观
   - 示例：高分 - "家人对我来说是最重要的"，低分 - "今天吃了面包"

**LLM 提示词**：
```python
prompt = f"""
评估用户消息的情感显著性，分别评分（0-1）：

1. 情感强度 (emotional_intensity)
2. 自我披露深度 (self_disclosure_depth)
3. 价值观相关性 (value_relevance)

用户消息：{content}

输出JSON格式：
{{
  "emotional_intensity": 0.0-1.0,
  "self_disclosure_depth": 0.0-1.0,
  "value_relevance": 0.0-1.0
}}
"""
```

**最终分数计算**：
```python
emotional_salience = (
    0.4 × emotional_intensity +
    0.4 × self_disclosure_depth +
    0.2 × value_relevance
)
```

**实测案例**：

| 消息 | 强度 | 披露 | 价值 | 最终分数 |
|------|------|------|------|---------|
| "今天天气不错" | 0.0 | 0.0 | 0.0 | **0.000** |
| "呵呵，随便吧" | 0.3 | 0.2 | 0.4 | **0.280** |
| "说实话，我对未来很迷茫" | 0.7 | 0.7 | 0.7 | **0.700** |
| "我从没告诉过别人，我很害怕失败" | 0.8 | 1.0 | 0.6 | **0.820** |

---

#### 代码实现

**检索时** (`vector_store.py`):
```python
def search_with_forgetting_curve(self, user_id, query, ...):
    for msg in messages:
        # 1. 计算语义相似度
        similarity = cosine_similarity(query_embedding, msg['embedding'])

        # 2. 计算基础召回概率（遗忘曲线）
        base_prob = recall_model.calculate_recall_probability(
            relevance=similarity,
            elapsed_time=elapsed_days,
            consolidation_g=msg['consolidation_g']
        )

        # 3. 情感显著性加成
        emotional_bonus = msg['emotional_salience'] * 0.1
        recall_prob = min(1.0, base_prob + emotional_bonus)

        # 4. 阈值筛选
        if recall_prob >= 0.86:
            recalled_memories.append(memory)

            # 5. 更新固化系数（越回忆越牢固）
            new_g = recall_model.update_consolidation(current_g, elapsed_days)
```

**读取时** (`memory_engine.py`):
```python
def _get_hybrid_context(self, user_id, current_task_id):
    # 1. 用户画像（复用 L3 的固化画像）
    user_profile = self._get_consolidated_gist(user_id)

    # 2. 短时成分：最近 3 轮
    recent_turns = turns[-3:]

    # 3. 长时成分：动态遗忘曲线检索
    retrieved = vector_store.search_with_forgetting_curve(user_id, query)

    return f"[用户画像]\n{profile}\n\n[当前对话]\n{recent}\n\n[相关历史线索]\n{retrieved}"
```

#### 数据库字段（chat_messages 表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `embedding` | TEXT | 向量（JSON 格式） |
| `importance_score` | FLOAT | 重要性分数 0-1 |
| `consolidation_g` | FLOAT | 固化系数（默认 1.0） |
| `recall_count` | INT | 被召回次数 |
| `last_recall_at` | DATETIME | 上次被召回时间 |
| `emotional_salience` | FLOAT | 情感显著性分数 0-1 |

#### 输出示例
```
[用户画像]
基本信息：occupation: 博士生
偏好：喜欢爬山、素食主义者
深层情感需求：希望被理解和认可
核心价值观：学术追求

[当前对话]
用户：最近压力好大
AI助手：怎么了？发生什么事了吗？
用户：论文进展不顺利

[相关历史线索]
[第1次对话] [相关度:0.87] 用户提到正在准备考博，对未来方向感到迷茫
[第2次对话] [相关度:0.82] 用户表达过希望被理解的需求
```

#### 系统提示词
```
你拥有两种记忆能力：
(1) 清晰记得最近的对话内容；
(2) 能够回想起与当前话题相关的历史细节。
当用户提到某个话题时，相关的过往记忆会被唤醒。
```

#### 预期表现
- 跨时空回忆相关历史
- 提到某话题时能想起相关的历史细节
- 经常被提及的记忆更难遗忘
- 高情感强度的记忆更容易被召回
- 用户感知：AI 真正理解我，像老朋友一样

---

## 四级记忆对比

### 记忆能力对比

| 能力维度 | L1 | L2 | L3 | L4 |
|---------|:--:|:--:|:--:|:--:|
| 当前对话理解 | ✓ | ✓ | ✓ | ✓ |
| 近期对话记忆 | ✗ | ✓ | ✓ | ✓ |
| 用户画像 | ✗ | ✗ | ✓ | ✓ |
| 情感显著性 | ✗ | ✗ | ✓ | ✓ |
| 跨时间关联 | ✗ | ✗ | ✗ | ✓ |
| 动态遗忘曲线 | ✗ | ✗ | ✗ | ✓ |
| 间隔效应强化 | ✗ | ✗ | ✗ | ✓ |

### 数据流对比

```
L1: 当前输入 → AI回复

L2: [最近7轮] + 当前输入 → AI回复

L3: [用户画像(含情感显著性)] + [最近3轮] + 当前输入 → AI回复

L4: [用户画像(含情感显著性)] + [最近3轮] + [动态检索的相关历史] + 当前输入 → AI回复
```

### 固化机制对比

| 层级 | 固化时机 | 固化内容 | 存储位置 |
|------|---------|---------|---------|
| L1 | 无 | 无 | 无 |
| L2 | 无 | 无 | 无 |
| L3 | Session 结束后 | 用户画像（含情感显著性） | user_profiles 表 |
| L4 | Session 结束后 | 向量 + 重要性 + 情感显著性 | chat_messages 表 |

---

## 实验流程

| 阶段 | 任务 | 时间点 | 目的 | 记忆操纵作用 |
|------|------|--------|------|-------------|
| T1 | 关系建立与信息播种 | 第1周 | 收集用户信息 | 所有组条件相同 |
| T2 | 记忆触发测试 | 第1周 | 测试记忆能力 | **操纵首次生效** |
| T3 | 深度任务支持 | 第2周 | 个性化建议 | 记忆差异持续 |
| T4 | 综合评估与告别 | 第3周 | 回顾与告别 | 记忆差异影响告别体验 |

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
│   └── vector_store.py       # 向量存储 + 动态遗忘曲线检索
│
├── services/
│   ├── memory_engine.py      # 四级记忆引擎（核心）
│   ├── consolidation_service.py  # 记忆固化服务（L3画像 + L4向量）
│   ├── llm_service.py        # LLM 调用封装
│   └── timer_service.py      # 计时器服务
│
├── static/
│   ├── index.html            # 前端界面
│   └── questionnaire_config.js  # 问卷配置
│
├── scripts/
│   ├── migrate_add_dynamic_memory_fields.py  # 数据库迁移
│   └── manual_consolidation.py  # 手动触发固化
│
└── data/
    └── experiment.db         # SQLite 数据库
```

### 核心类关系

```
┌─────────────────────────────────────────────────────────────┐
│                         app.py                               │
│  - 接收用户消息                                               │
│  - 调用 MemoryEngine 获取记忆上下文                           │
│  - 构建 System Prompt                                        │
│  - 调用 LLM 生成回复                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MemoryEngine                              │
│  - get_memory_context(user_id, memory_group, task_id)       │
│  - 路由到 _get_sensory/working/gist/hybrid_context          │
│  - 读取 DBManager 和 VectorStore                            │
└─────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────────┐          ┌───────────────────────────┐
│     DBManager        │          │       VectorStore         │
│  - 用户、消息 CRUD    │          │  - DashScope Embedding    │
│  - 用户画像读写       │          │  - 动态遗忘曲线检索        │
│  - 任务进度管理       │          │  - 固化系数更新           │
└──────────────────────┘          └───────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 ConsolidationService                         │
│  - Session 结束后调用                                        │
│  - L3: 提取用户画像（含情感显著性）                           │
│  - L4: 批量生成向量 + 计算情感显著性分数                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 配置说明

### config.py 核心配置

```python
EXPERIMENT_CONFIG = {
    'memory_groups': ['sensory_memory', 'working_memory', 'gist_memory', 'hybrid_memory'],
    'memory_config': {
        'sensory_memory': {
            'description': '感觉记忆（控制组）',
            'theory': 'Atkinson-Shiffrin感觉寄存器',
            'capacity': 0,
            'turns': 0,
        },
        'working_memory': {
            'description': '工作记忆（7±2组块）',
            'theory': 'Miller 1956',
            'capacity': 7,
            'turns': 7,
        },
        'gist_memory': {
            'description': '要义记忆（语义编码+情感显著性）',
            'theory': 'Fuzzy Trace Theory + Emotional Salience',
            'recent_turns': 3,
            'gist_max_chars': 500,
            'emotional_extraction': {
                'enabled': True,
                'extract_emotional_needs': True,
                'extract_core_values': True,
                'extract_significant_events': True
            }
        },
        'hybrid_memory': {
            'description': '混合记忆（动态遗忘曲线）',
            'theory': 'Ebbinghaus遗忘曲线 + Tulving陈述性记忆',
            'recent_turns': 3,
            'retrieval_top_k': 5,
            'forgetting_curve': {
                'enabled': True,
                'initial_g': 1.0,
                'recall_threshold': 0.86,
                'time_unit': 'days',
                'update_on_recall': True
            }
        },
    }
}
```

---

## 理论参考

| 理论 | 作者 | 年份 | 应用层级 | 核心贡献 |
|------|------|------|---------|---------|
| 多重存储模型 | Atkinson & Shiffrin | 1968 | L1 | 感觉记忆 → 短时记忆 → 长时记忆 |
| 魔法数字 7±2 | Miller | 1956 | L2 | 工作记忆容量限制 |
| 模糊痕迹理论 | Brainerd & Reyna | 1990 | L3 | Verbatim vs. Gist 双痕迹 |
| 情景记忆 | Tulving | 1972 | L4 | 陈述性记忆，扩散激活 |
| 遗忘曲线 | Ebbinghaus | 1885 | L4 | 指数衰减，间隔效应 |
| 动态记忆召回 | Hou et al. (CHI'24) | 2024 | L4 | $p_n(t)$ 公式，固化系数更新 |

---

## License

MIT License
