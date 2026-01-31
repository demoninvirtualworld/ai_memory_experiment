"""
记忆引擎 (Memory Engine)

基于认知心理学理论的四级记忆架构实现：
- L1 感觉记忆 (sensory_memory): 无编码，返回空
- L2 工作记忆 (working_memory): Miller 7±2，保留最近N轮
- L3 要义记忆 (gist_memory): Verbatim→Gist，近期原话+历史摘要
- L4 混合记忆 (hybrid_memory): 短时焦点+向量检索（Chroma）

所有数据操作通过 DBManager 完成
向量检索通过 VectorStore 完成
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime

from database import DBManager, ChatMessage
from database.vector_store import VectorStore, MemoryItem, get_vector_store
from config import Config


class MemoryEngine:
    """
    记忆引擎

    负责根据用户的记忆组别，从数据库提取并格式化历史对话上下文
    """

    # 从 config.py 读取配置
    MEMORY_CONFIG = Config.EXPERIMENT_CONFIG.get('memory_config', {})

    # 默认配置（如果 config.py 中没有）
    WORKING_MEMORY_TURNS = MEMORY_CONFIG.get('working_memory', {}).get('turns', 7)
    RECENT_VERBATIM_TURNS = MEMORY_CONFIG.get('gist_memory', {}).get('recent_turns', 3)
    RETRIEVAL_TOP_K = MEMORY_CONFIG.get('hybrid_memory', {}).get('retrieval_top_k', 3)
    GIST_MAX_CHARS = MEMORY_CONFIG.get('gist_memory', {}).get('gist_max_chars', 500)

    def __init__(self, db_manager: DBManager, llm_manager=None, vector_store: VectorStore = None):
        """
        初始化记忆引擎

        Args:
            db_manager: 数据库管理器实例
            llm_manager: LLM管理器（用于生成摘要，可选）
            vector_store: 向量存储实例（用于 L4 混合记忆，可选）
        """
        self.db = db_manager
        self.llm_manager = llm_manager
        self._current_query: Optional[str] = None
        # L4 混合记忆的向量存储
        self._vector_store = vector_store

    def set_current_query(self, query: str):
        """设置当前查询（用于 L4 混合记忆的相关性检索）"""
        self._current_query = query

    def get_memory_context(
        self,
        user_id: str,
        memory_group: str,
        current_task_id: int
    ) -> str:
        """
        获取记忆上下文

        根据记忆组别返回格式化的历史对话文本，可直接用于构建 System Prompt

        Args:
            user_id: 用户ID
            memory_group: 记忆组别 (sensory_memory, working_memory, gist_memory, hybrid_memory)
            current_task_id: 当前任务ID（用于过滤历史）

        Returns:
            格式化的记忆上下文字符串
        """
        # 路由到对应的记忆处理方法
        handlers = {
            'sensory_memory': self._get_sensory_context,
            'working_memory': self._get_working_context,
            'gist_memory': self._get_gist_context,
            'hybrid_memory': self._get_hybrid_context,
        }

        handler = handlers.get(memory_group)
        if handler:
            return handler(user_id, current_task_id)

        # 未知的记忆组别，返回空
        return ""

    # ============ L1: 感觉记忆 ============

    def _get_sensory_context(self, user_id: str, current_task_id: int) -> str:
        """
        L1: 感觉记忆 (Sensory Memory)

        心理学基础: Atkinson-Shiffrin 感觉寄存器
        - 信息未进入意识加工，无编码
        - 容量 = 0

        实现: 返回空字符串
        """
        return ""

    # ============ L2: 工作记忆 ============

    def _get_working_context(self, user_id: str, current_task_id: int) -> str:
        """
        L2: 工作记忆 (Working Memory)

        心理学基础: Miller (1956) 7±2 法则
        - 以组块(Chunk)为单位存储
        - 超出容量时发生位块替换(Displacement)

        实现: 保留最近 N 轮对话 (默认7轮)
        """
        # 获取当前任务之前的所有消息
        messages = self.db.get_messages_before_task(user_id, current_task_id)

        if not messages:
            return ""

        # 转换为轮次
        turns = self._messages_to_turns(messages)

        if not turns:
            return ""

        # 取最近 N 轮
        recent_turns = turns[-self.WORKING_MEMORY_TURNS:]

        # 格式化输出
        return self._format_turns(recent_turns)

    # ============ L3: 要义记忆 ============

    def _get_gist_context(self, user_id: str, current_task_id: int) -> str:
        """
        L3: 要义记忆 (Gist Memory)

        心理学基础: Fuzzy Trace Theory (Brainerd & Reyna)
        - Verbatim Trace: 精确但衰退快
        - Gist Trace: 语义本质，衰退慢

        实现:
        - 最近 3 轮: 保留 Verbatim (原话)
        - 更早历史: 转化为 Gist (要义摘要)
        """
        messages = self.db.get_messages_before_task(user_id, current_task_id)

        if not messages:
            return ""

        turns = self._messages_to_turns(messages)

        if not turns:
            return ""

        context_parts = []

        # 1. 更早的历史 → 读取固化的用户画像（Gist）
        if len(turns) > self.RECENT_VERBATIM_TURNS:
            # 优先读取固化的画像（避免实时生成延迟）
            gist = self._get_consolidated_gist(user_id)

            # 如果画像不存在，降级为实时生成
            if not gist:
                older_turns = turns[:-self.RECENT_VERBATIM_TURNS]
                gist = self._generate_gist_summary(older_turns)

            if gist:
                context_parts.append(f"[用户画像]\n{gist}")

        # 2. 最近 N 轮 → 保留原话 (Verbatim)
        recent_turns = turns[-self.RECENT_VERBATIM_TURNS:]
        if recent_turns:
            verbatim = self._format_turns(recent_turns)
            if verbatim:
                context_parts.append(f"[近期对话]\n{verbatim}")

        return "\n\n".join(context_parts)

    def _get_consolidated_gist(self, user_id: str) -> str:
        """
        读取固化的用户画像（L3 专用）

        Returns:
            格式化的画像文本，如果不存在则返回空字符串
        """
        try:
            profile = self.db.get_user_profile(user_id)

            if not profile or not any(profile.values()):
                return ""

            # 格式化画像为自然语言
            lines = []

            if profile.get('basic_info'):
                info = profile['basic_info']
                if info:
                    lines.append("基本信息：" + "，".join(f"{k}: {v}" for k, v in info.items()))

            if profile.get('preferences'):
                prefs = profile['preferences']
                if prefs:
                    lines.append("偏好：" + "、".join(prefs))

            if profile.get('constraints'):
                constraints = profile['constraints']
                if constraints:
                    lines.append("限制：" + "、".join(constraints))

            if profile.get('goals'):
                goals = profile['goals']
                if goals:
                    lines.append("目标：" + "、".join(goals))

            if profile.get('personality'):
                personality = profile['personality']
                if personality:
                    lines.append("性格：" + "、".join(personality))

            if profile.get('social'):
                social = profile['social']
                if social:
                    lines.append("社交：" + "、".join(social))

            return "\n".join(lines) if lines else ""

        except Exception as e:
            print(f"[MemoryEngine] 读取固化画像失败: {e}")
            return ""

    # ============ L4: 混合记忆 ============

    def _get_hybrid_context(self, user_id: str, current_task_id: int) -> str:
        """
        L4: 混合记忆 (Hybrid Long-term Memory)

        心理学基础: Tulving 陈述性记忆 + 扩散激活
        - 无限容量但受提取线索影响
        - 编码特异性原则

        实现:
        - 短时成分: 最近 3 轮 (当前焦点)
        - 长时成分: 向量加权检索 Top-K
          公式: Score = α·Recency + β·Similarity + γ·Importance
        """
        messages = self.db.get_messages_before_task(user_id, current_task_id)

        if not messages:
            return ""

        turns = self._messages_to_turns(messages)

        context_parts = []

        # 1. 短时成分: 最近 N 轮 (当前焦点)
        if turns:
            recent_turns = turns[-self.RECENT_VERBATIM_TURNS:]
            if recent_turns:
                recent_text = self._format_turns(recent_turns)
                if recent_text:
                    context_parts.append(f"[当前对话]\n{recent_text}")

        # 2. 长时成分: 向量加权检索相关历史
        query = self._current_query
        if query:
            # 尝试使用向量存储进行检索
            retrieved_memories = self._get_vector_search_v2(
                user_id=user_id,
                query=query,
                exclude_task_id=current_task_id
            )

            if retrieved_memories:
                retrieved_text = self._format_memory_items(retrieved_memories)
                if retrieved_text:
                    context_parts.append(f"[相关历史线索]\n{retrieved_text}")
            elif turns and len(turns) > self.RECENT_VERBATIM_TURNS:
                # 降级方案：关键词匹配
                older_turns = turns[:-self.RECENT_VERBATIM_TURNS]
                fallback = self._keyword_search(older_turns, query)
                if fallback:
                    fallback_text = self._format_turns_with_source(fallback)
                    if fallback_text:
                        context_parts.append(f"[相关历史线索]\n{fallback_text}")

        return "\n\n".join(context_parts)

    def _get_vector_search_v2(
        self,
        user_id: str,
        query: str,
        exclude_task_id: int = None
    ) -> List[MemoryItem]:
        """
        使用 VectorStore 进行加权向量检索

        公式: Score = α·Recency + β·Similarity + γ·Importance
        权重从 config.py MEMORY_OPERATIONS['hybrid_memory'] 读取

        Args:
            user_id: 用户ID
            query: 查询文本
            exclude_task_id: 排除的任务ID

        Returns:
            检索到的记忆列表
        """
        # 获取向量存储实例（传入 db_manager）
        vector_store = self._vector_store or get_vector_store(self.db)

        if not vector_store or not vector_store.db:
            return []

        try:
            # 调用加权检索
            results = vector_store.search_weighted(
                user_id=user_id,
                query=query,
                exclude_task_id=exclude_task_id,
                top_k=self.RETRIEVAL_TOP_K
            )
            return results

        except Exception as e:
            print(f"[MemoryEngine] 向量检索失败: {e}")
            return []

    def _format_memory_items(self, memories: List[MemoryItem]) -> str:
        """
        格式化向量检索结果

        Args:
            memories: MemoryItem 列表

        Returns:
            格式化的文本
        """
        if not memories:
            return ""

        lines = []
        for mem in memories:
            task_label = f"第{mem.task_id}次对话" if mem.task_id else "历史"
            # 显示分数信息（调试用，可移除）
            score_info = f"[相关度:{mem.similarity_score:.2f}]"
            lines.append(f"[{task_label}] {score_info} {mem.content}")

        return "\n".join(lines)

    def _get_vector_search(
        self,
        user_id: str,
        turns: List[Dict],
        query: Optional[str]
    ) -> List[Dict]:
        """
        向量检索相关历史

        TODO: 接入 Chroma 向量数据库实现真正的语义检索

        当前实现: 降级为关键词匹配 + 时间衰减

        Args:
            user_id: 用户ID
            turns: 历史轮次列表
            query: 当前查询文本

        Returns:
            检索到的相关轮次列表 (Top-K)
        """
        # TODO: 接入 Chroma 实现向量检索
        # 示例代码（后续实现）:
        # ```
        # from database.vector_store import VectorStore
        # vector_store = VectorStore()
        # results = vector_store.search(
        #     user_id=user_id,
        #     query=query,
        #     top_k=self.RETRIEVAL_TOP_K
        # )
        # return results
        # ```

        # 当前降级方案: 关键词匹配
        return self._keyword_search(turns, query)

    def _keyword_search(
        self,
        turns: List[Dict],
        query: Optional[str]
    ) -> List[Dict]:
        """
        降级方案: 关键词匹配检索

        计算公式: score = 0.5 * relevance + 0.3 * recency
        """
        if not turns:
            return []

        # 如果没有查询词，返回最近的几轮
        if not query:
            return turns[-self.RETRIEVAL_TOP_K:]

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 1]

        scored_turns = []
        for i, turn in enumerate(turns):
            # 构建轮次文本
            text = self._turn_to_text(turn).lower()

            # 关键词匹配分数
            relevance_score = sum(1 for word in query_words if word in text)

            # 新鲜度分数
            recency_score = i / len(turns) if turns else 0

            # 综合分数
            combined_score = 0.5 * relevance_score + 0.3 * recency_score

            scored_turns.append({
                **turn,
                '_score': combined_score
            })

        # 按分数排序，取 Top-K
        scored_turns.sort(key=lambda x: x['_score'], reverse=True)
        return scored_turns[:self.RETRIEVAL_TOP_K]

    # ============ 辅助方法 ============

    def _messages_to_turns(self, messages: List[ChatMessage]) -> List[Dict]:
        """
        将消息列表转换为轮次列表

        一轮 = 一次用户消息 + 一次AI回复
        """
        turns = []
        current_turn = {'user': None, 'assistant': None, 'task_id': None}

        for msg in messages:
            if msg.is_user:
                # 如果当前轮已有用户消息，先保存
                if current_turn['user'] is not None:
                    turns.append(current_turn)
                    current_turn = {'user': None, 'assistant': None, 'task_id': None}
                current_turn['user'] = msg.content
                current_turn['task_id'] = msg.task_id
            else:
                current_turn['assistant'] = msg.content
                if current_turn['task_id'] is None:
                    current_turn['task_id'] = msg.task_id
                # AI回复后，一轮结束
                if current_turn['user'] is not None:
                    turns.append(current_turn)
                    current_turn = {'user': None, 'assistant': None, 'task_id': None}

        # 处理最后一个不完整的轮次
        if current_turn['user'] is not None:
            turns.append(current_turn)

        return turns

    def _turn_to_text(self, turn: Dict) -> str:
        """将轮次转换为纯文本（用于关键词匹配）"""
        parts = []
        if turn.get('user'):
            parts.append(turn['user'])
        if turn.get('assistant'):
            parts.append(turn['assistant'])
        return " ".join(parts)

    def _format_turns(self, turns: List[Dict]) -> str:
        """格式化轮次为对话文本"""
        lines = []
        for turn in turns:
            if turn.get('user'):
                lines.append(f"用户：{turn['user']}")
            if turn.get('assistant'):
                lines.append(f"AI助手：{turn['assistant']}")
        return "\n".join(lines)

    def _format_turns_with_source(self, turns: List[Dict]) -> str:
        """格式化轮次（带来源标记，用于混合记忆）"""
        lines = []
        for turn in turns:
            task_id = turn.get('task_id', '?')
            if turn.get('user'):
                lines.append(f"[第{task_id}次对话] 用户：{turn['user']}")
            if turn.get('assistant'):
                lines.append(f"[第{task_id}次对话] AI助手：{turn['assistant']}")
        return "\n".join(lines)

    def _generate_gist_summary(self, turns: List[Dict]) -> str:
        """
        生成要义摘要 (Gist Summary)

        将 Verbatim (字面信息) 转化为 Gist (语义要义)
        """
        if not turns:
            return ""

        # 构建对话文本
        conversation_text = self._format_turns(turns)

        # 如果有 LLM manager，使用 LLM 生成摘要
        if self.llm_manager and hasattr(self.llm_manager, 'generate_summary'):
            try:
                summary = self.llm_manager.generate_summary(
                    conversation_text,
                    self.GIST_MAX_CHARS
                )
                if summary:
                    return summary
            except Exception as e:
                print(f"[MemoryEngine] LLM摘要生成失败: {e}")

        # 降级方案: 提取关键信息
        return self._extract_key_information(conversation_text)

    def _extract_key_information(self, text: str) -> str:
        """
        降级方案: 从文本中提取关键信息

        用于 LLM 不可用时的摘要生成
        """
        lines = text.split('\n')

        # 提取用户发言中的关键信息
        user_info = []
        for line in lines:
            if line.startswith('用户：'):
                content = line[3:].strip()
                if len(content) > 15:
                    user_info.append(content)

        # 限制数量
        if len(user_info) > 5:
            user_info = user_info[:3] + user_info[-2:]

        if user_info:
            summary = "用户曾提到：" + "；".join(user_info[:3])
            if len(summary) > self.GIST_MAX_CHARS:
                summary = summary[:self.GIST_MAX_CHARS] + "..."
            return summary

        return ""

    # ============ 统计方法 ============

    def get_memory_stats(self, user_id: str) -> Dict:
        """获取用户的记忆统计信息"""
        messages = self.db.get_user_all_messages(user_id)
        turns = self._messages_to_turns(messages)

        return {
            'total_messages': len(messages),
            'total_turns': len(turns),
            'user_messages': sum(1 for m in messages if m.is_user),
            'ai_messages': sum(1 for m in messages if not m.is_user),
        }
