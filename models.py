import json
import os
from datetime import datetime
from typing import Dict, List, Any



class User:
    def __init__(self, user_id: str, name: str, memory_group: str):
        self.id = user_id
        self.name = name
        self.memory_group = memory_group
        self.settings = {
            'responseStyle': 'high',
            'aiAvatar': 'human'
        }
        self.current_task_id = None
        self.task_progress = {}
        self.created_at = datetime.now().isoformat()
        # 实验特定字段
        self.demographics = {}
        self.experiment_phase = 1  # 1-4阶段
        self.questionnaire_responses = {}

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'memory_group': self.memory_group,
            'settings': self.settings,
            'current_task_id': self.current_task_id,
            'task_progress': self.task_progress,
            'created_at': self.created_at,
            'demographics': self.demographics,
            'experiment_phase': self.experiment_phase,
            'questionnaire_responses': self.questionnaire_responses
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(data['id'], data['name'], data['memory_group'])
        user.settings = data.get('settings', {})
        user.current_task_id = data.get('current_task_id')
        user.task_progress = data.get('task_progress', {})
        user.created_at = data.get('created_at')
        user.demographics = data.get('demographics', {})
        user.experiment_phase = data.get('experiment_phase', 1)
        user.questionnaire_responses = data.get('questionnaire_responses', {})
        return user


class Task:
    def __init__(self, task_id: int, title: str, description: str, content: str, time_point: int):
        self.id = task_id
        self.title = title
        self.description = description
        self.content = content
        self.time_point = time_point
        self.phase = self._get_phase(time_point)

    def _get_phase(self, time_point):
        phases = {
            1: "关系建立与信息播种",
            3: "记忆触发测试",
            10: "深度任务支持",
            17: "综合评估与告别"
        }
        return phases.get(time_point, "未知阶段")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'content': self.content,
            'time_point': self.time_point,
            'phase': self.phase
        }


class Document:
    def __init__(self, title: str = "", content: str = ""):
        self.title = title
        self.content = content
        self.submitted = False
        self.timestamp = datetime.now().isoformat()
        self.questionnaire_data = {}  # 存储问卷数据

    def to_dict(self):
        return {
            'title': self.title,
            'content': self.content,
            'submitted': self.submitted,
            'timestamp': self.timestamp,
            'questionnaire_data': self.questionnaire_data
        }

    @classmethod
    def from_dict(cls, data):
        doc = cls(data.get('title', ''), data.get('content', ''))
        doc.submitted = data.get('submitted', False)
        doc.timestamp = data.get('timestamp')
        doc.questionnaire_data = data.get('questionnaire_data', {})
        return doc


class ChatMessage:
    def __init__(self, content: str, is_user: bool, message_id: str = None):
        self.message_id = message_id or f"msg_{datetime.now().timestamp()}"
        self.content = content
        self.is_user = is_user
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            'message_id': self.message_id,
            'content': self.content,
            'is_user': self.is_user,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data):
        msg = cls(data['content'], data['is_user'], data['message_id'])
        msg.timestamp = data['timestamp']
        return msg


class QuestionnaireResponse:
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.responses = {}
        self.submitted_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'responses': self.responses,
            'submitted_at': self.submitted_at
        }

    @classmethod
    def from_dict(cls, data):
        response = cls(data['task_id'])
        response.responses = data.get('responses', {})
        response.submitted_at = data.get('submitted_at')
        return response


class MemoryContext:
    """
    记忆上下文管理

    基于认知心理学理论的四级记忆架构：
    - L1 感觉记忆 (sensory_memory): 无编码，仅当前输入
    - L2 工作记忆 (working_memory): Miller 7±2 法则，保留最近7轮
    - L3 要义记忆 (gist_memory): Verbatim→Gist转化，最近3轮原话+历史要义
    - L4 混合记忆 (hybrid_memory): 最近3轮+向量检索相关历史
    """

    # 记忆配置常量
    WORKING_MEMORY_TURNS = 7   # Miller's 7±2
    RECENT_VERBATIM_TURNS = 3  # 保留原话的轮数
    RETRIEVAL_TOP_K = 3        # 检索的历史片段数
    GIST_MAX_CHARS = 500       # 要义摘要最大字数

    def __init__(self, user_id: str, memory_group: str, llm_manager=None):
        self.user_id = user_id
        self.memory_group = memory_group
        self.conversation_history = []  # 所有历史对话
        self.llm_manager = llm_manager  # 用于生成要义摘要和计算相似度

    def add_conversation(self, task_id: int, conversation: List[Dict]):
        """添加对话记录（按轮次存储）"""
        # 将对话转换为轮次格式
        turns = self._extract_turns(conversation)
        self.conversation_history.append({
            'task_id': task_id,
            'conversation': conversation,
            'turns': turns,
            'timestamp': datetime.now().isoformat()
        })

    def _extract_turns(self, conversation: List[Dict]) -> List[Dict]:
        """
        将消息列表转换为轮次列表
        一轮 = 一次用户消息 + 一次AI回复
        """
        turns = []
        current_turn = {'user': None, 'assistant': None}

        for msg in conversation:
            if msg.get('is_user', False):
                # 如果当前轮已有用户消息，先保存当前轮
                if current_turn['user'] is not None:
                    turns.append(current_turn)
                    current_turn = {'user': None, 'assistant': None}
                current_turn['user'] = msg.get('content', '')
            else:
                current_turn['assistant'] = msg.get('content', '')
                # AI回复后，一轮结束
                if current_turn['user'] is not None:
                    turns.append(current_turn)
                    current_turn = {'user': None, 'assistant': None}

        # 处理最后一个不完整的轮次
        if current_turn['user'] is not None:
            turns.append(current_turn)

        return turns

    def get_context_for_task(self, current_task_id: int) -> str:
        """
        根据记忆组别获取对应的记忆上下文

        记忆读取公式: m* = argmin(α·s_rec + β·s_rel + γ·s_imp)
        - sensory_memory: 无读取
        - working_memory: α=1 (仅新鲜度)
        - gist_memory: γ=1 (仅重要性/语义压缩)
        - hybrid_memory: α,β,γ混合加权
        """
        if self.memory_group == "sensory_memory":
            return self._get_sensory_memory_context()
        elif self.memory_group == "working_memory":
            return self._get_working_memory_context()
        elif self.memory_group == "gist_memory":
            return self._get_gist_memory_context()
        elif self.memory_group == "hybrid_memory":
            return self._get_hybrid_memory_context()
        else:
            # 兼容旧版本的记忆组名称
            return self._handle_legacy_memory_group(current_task_id)

    def _get_sensory_memory_context(self) -> str:
        """
        L1: 感觉记忆 (Sensory Memory)

        心理学基础: Atkinson-Shiffrin 感觉寄存器
        - 信息未进入意识加工，无编码
        - 容量 = 0

        实现: 返回空字符串，每轮对话都是全新开始
        """
        return ""

    def _get_working_memory_context(self) -> str:
        """
        L2: 工作记忆 (Working Memory)

        心理学基础: Miller (1956) 7±2 法则
        - 以组块(Chunk)为单位存储
        - 超出容量时发生位块替换(Displacement)

        实现: 保留最近 7 轮对话
        读取操作: α=1 (仅新鲜度)
        """
        # 收集所有历史轮次
        all_turns = []
        for task_data in self.conversation_history:
            for turn in task_data.get('turns', []):
                all_turns.append({
                    'task_id': task_data['task_id'],
                    'turn': turn
                })

        if not all_turns:
            return ""

        # 按新鲜度取最近 7 轮
        recent_turns = all_turns[-self.WORKING_MEMORY_TURNS:]

        # 格式化输出
        context_lines = []
        for item in recent_turns:
            turn = item['turn']
            if turn['user']:
                context_lines.append(f"用户：{turn['user']}")
            if turn['assistant']:
                context_lines.append(f"AI助手：{turn['assistant']}")

        return "\n".join(context_lines)

    def _get_gist_memory_context(self) -> str:
        """
        L3: 要义记忆 (Gist Memory)

        心理学基础: Fuzzy Trace Theory (Brainerd & Reyna)
        - Verbatim Trace (字面痕迹): 精确但衰退快
        - Gist Trace (要义痕迹): 语义本质，衰退慢

        实现:
        - 最近 3 轮: 保留 Verbatim (原话)
        - 更早历史: 转化为 Gist (要义摘要)

        读取操作: γ=1 (仅重要性/语义)
        """
        # 收集所有历史轮次
        all_turns = []
        for task_data in self.conversation_history:
            for turn in task_data.get('turns', []):
                all_turns.append(turn)

        if not all_turns:
            return ""

        context_parts = []

        # 1. 更早的历史 → 要义摘要 (Gist)
        if len(all_turns) > self.RECENT_VERBATIM_TURNS:
            older_turns = all_turns[:-self.RECENT_VERBATIM_TURNS]
            gist = self._generate_gist_summary(older_turns)
            if gist:
                context_parts.append(f"[历史要义]\n{gist}")

        # 2. 最近 3 轮 → 保留原话 (Verbatim)
        recent_turns = all_turns[-self.RECENT_VERBATIM_TURNS:]
        if recent_turns:
            verbatim_lines = []
            for turn in recent_turns:
                if turn['user']:
                    verbatim_lines.append(f"用户：{turn['user']}")
                if turn['assistant']:
                    verbatim_lines.append(f"AI助手：{turn['assistant']}")
            if verbatim_lines:
                context_parts.append(f"[近期对话]\n" + "\n".join(verbatim_lines))

        return "\n\n".join(context_parts)

    def _get_hybrid_memory_context(self, current_query: str = None) -> str:
        """
        L4: 混合记忆 (Hybrid Long-term Memory)

        心理学基础: Tulving 陈述性记忆
        - 无限容量但受提取线索(Retrieval Cues)影响
        - 编码特异性原则: 提取线索需匹配编码时的线索

        实现:
        - 短时成分: 最近 3 轮 (当前焦点)
        - 长时成分: 基于相关性检索 Top-K 历史片段

        读取操作: α,β,γ 混合加权
        """
        # 收集所有历史轮次（带task_id标记）
        all_turns_with_meta = []
        for task_data in self.conversation_history:
            task_id = task_data['task_id']
            for idx, turn in enumerate(task_data.get('turns', [])):
                all_turns_with_meta.append({
                    'task_id': task_id,
                    'turn_idx': idx,
                    'turn': turn,
                    'text': self._turn_to_text(turn)
                })

        if not all_turns_with_meta:
            return ""

        context_parts = []

        # 1. 短时成分: 最近 3 轮 (当前焦点)
        recent_items = all_turns_with_meta[-self.RECENT_VERBATIM_TURNS:]
        recent_indices = set(range(len(all_turns_with_meta) - self.RECENT_VERBATIM_TURNS, len(all_turns_with_meta)))

        if recent_items:
            recent_lines = []
            for item in recent_items:
                turn = item['turn']
                if turn['user']:
                    recent_lines.append(f"用户：{turn['user']}")
                if turn['assistant']:
                    recent_lines.append(f"AI助手：{turn['assistant']}")
            context_parts.append(f"[当前对话]\n" + "\n".join(recent_lines))

        # 2. 长时成分: 检索相关历史
        # 排除已在短时成分中的轮次
        older_items = [item for i, item in enumerate(all_turns_with_meta)
                       if i not in recent_indices]

        if older_items:
            # 简化版相关性检索：基于关键词匹配
            # 实际部署时可替换为向量数据库检索
            retrieved = self._retrieve_relevant_turns(older_items, current_query)

            if retrieved:
                retrieved_lines = []
                for item in retrieved:
                    turn = item['turn']
                    task_id = item['task_id']
                    if turn['user']:
                        retrieved_lines.append(f"[第{task_id}次对话] 用户：{turn['user']}")
                    if turn['assistant']:
                        retrieved_lines.append(f"[第{task_id}次对话] AI助手：{turn['assistant']}")
                context_parts.append(f"[相关历史记忆]\n" + "\n".join(retrieved_lines))

        return "\n\n".join(context_parts)

    def _turn_to_text(self, turn: Dict) -> str:
        """将轮次转换为文本"""
        parts = []
        if turn.get('user'):
            parts.append(turn['user'])
        if turn.get('assistant'):
            parts.append(turn['assistant'])
        return " ".join(parts)

    def _generate_gist_summary(self, turns: List[Dict]) -> str:
        """
        生成要义摘要 (Gist Summary)

        将 Verbatim (字面信息) 转化为 Gist (语义要义)
        """
        if not turns:
            return ""

        # 构建对话文本
        conversation_text = []
        for turn in turns:
            if turn.get('user'):
                conversation_text.append(f"用户：{turn['user']}")
            if turn.get('assistant'):
                conversation_text.append(f"AI助手：{turn['assistant']}")

        full_text = "\n".join(conversation_text)

        # 如果有 LLM manager，使用 LLM 生成摘要
        if self.llm_manager:
            try:
                summary = self.llm_manager.generate_summary(full_text, self.GIST_MAX_CHARS)
                if summary:
                    return summary
            except Exception as e:
                print(f"LLM摘要生成失败: {e}")

        # 降级方案：提取关键信息
        return self._extract_key_information(full_text)

    def _extract_key_information(self, text: str) -> str:
        """
        降级方案：从文本中提取关键信息
        用于 LLM 不可用时的摘要生成
        """
        lines = text.split('\n')

        # 提取用户发言中的关键信息
        user_info = []
        for line in lines:
            if line.startswith('用户：'):
                content = line[3:].strip()
                # 保留较长的、包含实质内容的句子
                if len(content) > 15:
                    user_info.append(content)

        # 限制长度
        if len(user_info) > 5:
            user_info = user_info[:3] + user_info[-2:]

        if user_info:
            summary = "用户曾提到：" + "；".join(user_info[:3])
            if len(summary) > self.GIST_MAX_CHARS:
                summary = summary[:self.GIST_MAX_CHARS] + "..."
            return summary

        return ""

    def _retrieve_relevant_turns(self, turns: List[Dict], query: str = None) -> List[Dict]:
        """
        检索相关的历史轮次

        简化版实现：基于时间衰减 + 关键词匹配
        实际部署时应替换为向量数据库检索
        """
        if not turns:
            return []

        # 如果没有查询词，返回最近的几轮（按新鲜度）
        if not query:
            return turns[-self.RETRIEVAL_TOP_K:]

        # 计算每个轮次的相关性分数
        scored_turns = []
        for i, item in enumerate(turns):
            text = item['text'].lower()
            query_lower = query.lower()

            # 简单的关键词匹配分数
            relevance_score = 0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 1 and word in text:
                    relevance_score += 1

            # 新鲜度分数（越新越高）
            recency_score = i / len(turns)

            # 综合分数 (β=0.5 相关性, α=0.3 新鲜度)
            combined_score = 0.5 * relevance_score + 0.3 * recency_score

            scored_turns.append({
                **item,
                'score': combined_score
            })

        # 按分数排序，取 Top-K
        scored_turns.sort(key=lambda x: x['score'], reverse=True)
        return scored_turns[:self.RETRIEVAL_TOP_K]

    def _handle_legacy_memory_group(self, current_task_id: int) -> str:
        """处理旧版本的记忆组名称（向后兼容）"""
        legacy_mapping = {
            'no_memory': 'sensory_memory',
            'short_memory': 'working_memory',
            'medium_memory': 'gist_memory',
            'long_memory': 'hybrid_memory',
        }

        new_group = legacy_mapping.get(self.memory_group)
        if new_group:
            self.memory_group = new_group
            return self.get_context_for_task(current_task_id)

        return ""

    def set_current_query(self, query: str):
        """设置当前查询（用于混合记忆的相关性检索）"""
        self._current_query = query

    def get_all_turns_for_embedding(self) -> List[Dict]:
        """
        获取所有轮次用于向量嵌入（为未来向量数据库集成预留）
        """
        all_turns = []
        for task_data in self.conversation_history:
            task_id = task_data['task_id']
            for idx, turn in enumerate(task_data.get('turns', [])):
                all_turns.append({
                    'task_id': task_id,
                    'turn_idx': idx,
                    'turn': turn,
                    'text': self._turn_to_text(turn),
                    'timestamp': task_data.get('timestamp')
                })
        return all_turns