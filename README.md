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

- **来源**: Tulving (1972) 陈述性记忆 · Ebbinghaus 遗忘曲线 · CHI'24 Hou et al. 动态记忆召回
- **核心原理**:
  - 每条历史消息都有一个**召回概率**，随时间自然衰减
  - 被召回的记忆获得**固化强化**，下次更难遗忘（间隔效应）
  - 情感显著性高的记忆，初始固化强度更高、召回时相关度更强

#### 实现方式

```
当前查询 → [用户画像(L3)] + [最近3轮] + [动态遗忘曲线检索] → AI回复
```

---

#### 理解固化系数 g_n（最重要的概念）

**g_n 是什么？**

可以把 g_n 理解为一条记忆的**抗遗忘强度**：

```
g_n 越大 → 记忆衰减越慢 → 间隔很久后依然可能被召回
g_n 越小 → 记忆衰减越快 → 几天后就会低于召回阈值
```

**g_n 如何随时间演化？**

每条消息在首次固化时获得一个初始值 g_0，之后每次被成功召回，g_n 就会增大一次：

```
g_0（首次固化）
  ↓ 第1次被召回后
g_1 = g_0 + S(t₁)
  ↓ 第2次被召回后
g_2 = g_1 + S(t₂)
  ↓ ... 滚雪球式增长
```

其中 S(t) = tanh(t/2)，间隔越长、固化增量越大（间隔效应）。

**具体数值示例**（本实验参数，平均间隔 2.5 天）：

| 时间节点 | 普通记忆 g_n | 高情感记忆 g_n（e=1.0） |
|---------|------------|----------------------|
| 第1次会话后（g_0） | **3.0** | **4.5** |
| 第2周（第4次会话） | ≈ 6.4 | ≈ 9.6 |
| 第3周（第8次会话） | ≈ 9.8 | ≈ 14.7 |
| 第4周（第12次会话）| ≈ 13.1 | ≈ 19.7 |

这就是论文要展示的**"滚雪球"效应**：核心情感记忆在4周后的 g_n 约是初始值的4倍，意味着即使间隔10天也不会被遗忘。

---

#### 理解召回概率与阈值

**召回概率公式**（CHI'24 Hou et al. 公式8）：

$$p_n(t) = \frac{1 - \exp(-r_{eff} \cdot e^{-t/g_n})}{1 - e^{-1}}$$

三个输入参数的直觉含义：

| 参数 | 含义 | 范围 | 效果 |
|------|------|------|------|
| $r_{eff}$ | 这条记忆与当前查询的语义相关度（含情感调制） | 0~1 | 越高越容易被想起 |
| $t$ | 距上次被召回的天数 | ≥0 | 越大越容易被遗忘 |
| $g_n$ | 固化强度 | ≥3.0 | 越大衰减越慢 |

**阈值 k=0.60 的意义**：只有 p_n(t) ≥ 0.60 的记忆才会被检索出来提供给 AI。

**实验节奏下的关键数值**（适配每周3次、间隔2~3天）：

| 场景 | r_eff | t | g_n | p_n(t) | 是否召回？ |
|------|-------|---|-----|--------|---------|
| 高相关，2天后，普通记忆 | 1.0 | 2d | 3.0 | **0.633** | ✅ 召回 |
| 高相关，3天后，普通记忆 | 1.0 | 3d | 3.0 | 0.487 | ❌ 遗忘 |
| 高相关，3天后，高情感记忆 | 1.0 | 3d | 4.5 | **0.633** | ✅ 召回 |
| 中等相关，2天后 | 0.7 | 2d | 3.0 | 0.478 | ❌ 遗忘 |
| 第4周高情感核心记忆（多次召回后） | 0.8 | 3d | 19.7 | **0.762** | ✅ 召回 |

**直觉解读**：高情感记忆因为 g_0=4.5 更大，在第一次"周末3天间隔"就能跨越阈值被召回；而普通记忆需要至少被主动提及2~3次（g_n 增长后）才能具备同等的抗遗忘能力。

---

#### 核心公式完整体系

**1. 情感调制相关度**（召回层，本实验扩展）：

$$r_{eff} = \min\!\left(1.0,\; r \times (1 + 0.3 \cdot e_{salience})\right)$$

将情感因子融入语义相关度内部，保持遗忘曲线的数学封闭性。

**2. 召回概率**（CHI'24 公式8）：

$$p_n(t) = \frac{1 - \exp(-r_{eff} \cdot e^{-t/g_n})}{1 - e^{-1}}$$

**3. 初始固化系数**（固化层，本实验扩展）：

$$g_0 = 3.0 + 1.5 \times e_{salience}$$

无情感(e=0)：g₀=3.0，覆盖2天间隔；高情感(e=1)：g₀=4.5，覆盖3天间隔。

**4. 固化系数更新**（再固化层，CHI'24 公式9 + 情感加速）：

$$g_n = g_{n-1} + S(t) \times (1 + 0.5 \cdot e_{salience}), \quad S(t) = \tanh\!\left(\frac{t}{2}\right)$$

S(t) 取值范围 [0,1)，间隔越长固化增量越大，模拟间隔效应。

**符号表**：

| 符号 | 含义 |
|------|------|
| $r$ | 语义相似度（cosine similarity，0~1） |
| $e_{salience}$ | 情感显著性分数（LLM三维评估，0~1） |
| $r_{eff}$ | 情感调制后的有效相关度（0~1） |
| $t$ | 距上次召回的天数 |
| $g_n$ | 第 n 次召回后的固化系数 |
| $S(t)$ | 间隔效应函数，= tanh(t/2) |

---

#### 情感显著性评估（LLM三维打分）

采用**纯 LLM 方法**评估（当前配置 `method='llm'`）。LLM 不可用时返回 0.0（不施加情感加成），不降级为规则方法，保证分数量纲一致。

**三个评估维度**（权重和 = 1.0）：

| 维度 | 权重 | 高分示例 | 低分示例 |
|------|------|---------|---------|
| 情感强度 (Intensity) | 0.4 | "我真的崩溃了" | "今天天气不错" |
| 自我披露深度 (Disclosure) | 0.4 | "我从没告诉过别人..." | "我是学生" |
| 价值观相关性 (Value) | 0.2 | "家人是我最重要的事" | "今天吃了面包" |

**实测案例**：

| 消息 | 强度 | 披露 | 价值 | 情感分 e |
|------|------|------|------|---------|
| "今天天气不错" | 0.0 | 0.0 | 0.0 | **0.00** |
| "说实话，我对未来很迷茫" | 0.7 | 0.7 | 0.7 | **0.70** |
| "我从没告诉过别人，我很害怕失败" | 0.8 | 1.0 | 0.6 | **0.82** |

情感分对 g_0 的影响：

```
e=0.00 → g_0 = 3.0 + 1.5×0.00 = 3.0（普通记忆）
e=0.70 → g_0 = 3.0 + 1.5×0.70 = 4.05
e=0.82 → g_0 = 3.0 + 1.5×0.82 = 4.23（近乎覆盖3天间隔）
```

---

#### 当前参数配置

| 配置项 | 值 | 设计依据 |
|--------|-----|---------|
| `initial_g` | **3.0** | 适配实验2天最短间隔（r=1时 p≈0.633 > 0.60） |
| `recall_threshold` | **0.60** | 在2~3天间隔下产生有意义的记忆分化 |
| `emotional_α` (g₀公式) | **1.5** | 使高情感记忆(e=1) g₀=4.5，覆盖3天间隔 |
| `emotional_α` (r_eff公式) | **0.3** | 高情感记忆召回相关度最多提升30% |
| `emotional_α` (再固化公式) | **0.5** | 高情感记忆固化速度最多提升50% |
| `recent_turns` | 3 | 最近3轮（当前焦点） |
| `retrieval_top_k` | 5 | 超阈值记忆按概率取前5 |
| `time_unit` | days | 与实验间隔单位一致 |

---

#### 代码实现

**检索时** (`vector_store.py`):
```python
def search_with_forgetting_curve(self, user_id, query, ...):
    for msg in messages:
        # 1. 语义相似度
        similarity = cosine_similarity(query_embedding, msg['embedding'])
        emotional_salience = msg.get('emotional_salience', 0.0)

        # 2. 情感调制相关度（情感融入曲线内部，不外加）
        r_effective = min(1.0, similarity * (1 + 0.3 * emotional_salience))

        # 3. 计算召回概率（完整遗忘曲线）
        recall_prob = recall_model.calculate_recall_probability(
            relevance=r_effective,
            elapsed_time=elapsed_days,
            consolidation_g=msg['consolidation_g']
        )

        # 4. 阈值筛选
        if recall_prob >= 0.60:
            recalled_memories.append(memory)

            # 5. 召回后更新固化系数（情感加速）
            new_g = recall_model.update_consolidation(
                current_g, elapsed_days, emotional_salience=emotional_salience
            )
```

**固化时** (`consolidation_service.py`):
```python
# 情感显著性 LLM 评估
emotional_salience = self._calculate_emotional_salience_llm(content, is_user)

# 初始固化系数（情感加成）
initial_g = 3.0 + 1.5 * emotional_salience
msg.consolidation_g = initial_g
```

**读取时** (`memory_engine.py`):
```python
def _get_hybrid_context(self, user_id, current_task_id):
    # 1. 用户画像（复用 L3 的固化画像）
    user_profile = self._get_consolidated_gist(user_id)

    # 2. 短时成分：最近 3 轮
    recent_turns = turns[-3:]

    # 3. 长时成分：动态遗忘曲线检索（仅返回 p_n(t) ≥ 0.60 的记忆）
    retrieved = vector_store.search_with_forgetting_curve(user_id, query)

    return f"[用户画像]\n{profile}\n\n[当前对话]\n{recent}\n\n[相关历史线索]\n{retrieved}"
```

#### 数据库字段（chat_messages 表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `embedding` | TEXT | 向量（JSON 格式） |
| `importance_score` | FLOAT | 重要性分数 0-1 |
| `consolidation_g` | FLOAT | 固化系数（初始 3.0，随召回增长） |
| `recall_count` | INT | 被召回次数 |
| `last_recall_at` | DATETIME | 上次被召回时间 |
| `emotional_salience` | FLOAT | 情感显著性分数 0-1（LLM评估） |

#### 输出示例
```
[用户画像]
基本信息：occupation: 博士生
偏好：喜欢爬山、素食主义者
深层情感需求：希望被理解和认可
核心价值观：学术追求
重要事件：对未来职业方向感到迷茫（焦虑）

[当前对话]
用户：最近压力好大
AI助手：怎么了？发生什么事了吗？
用户：论文进展不顺利

[相关历史线索]（召回概率 ≥ 0.60）
[Task 1] [p=0.71] 用户提到正在准备考博，对未来方向感到迷茫
[Task 2] [p=0.64] 用户表达过希望被理解的需求
```

#### 预期表现
- 跨任务召回与当前话题相关的历史细节
- 高情感记忆（如"第一次说出来自己很迷茫"）在4周后依然可被唤醒
- 同一话题被多次提及后，对应记忆 g_n 持续增长，回忆更稳定
- 用户感知：AI 真正记得我说过的重要的话，像老朋友一样

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
                'initial_g': 3.0,       # 适配2天实验间隔
                'recall_threshold': 0.60, # 适配每周3次实验节奏
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
