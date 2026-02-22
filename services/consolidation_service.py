"""
记忆固化服务 (Consolidation Service)

基于 He et al. (2024) 的理论：记忆固化应在 Session 结束后离线运行
融合 CHI'24 Hou et al. 的情感显著性提取

功能：
- L3: 提取用户画像增量并更新（含情感显著性）
- L4: 批量生成向量并存储（含情感显著性分数）
"""

import json
from typing import Dict, List, Optional
from datetime import datetime

from database import DBManager
from database.vector_store import VectorStore, get_vector_store
from config import Config


class ConsolidationService:
    """
    记忆固化服务

    在每次 Session（任务）结束后调用，将短期记忆转化为长期记忆
    """

    def __init__(self, db_manager: DBManager, llm_manager=None):
        """
        初始化固化服务

        Args:
            db_manager: 数据库管理器
            llm_manager: LLM 管理器（用于生成摘要）
        """
        self.db = db_manager
        self.llm = llm_manager
        self.vector_store = get_vector_store(db_manager)

    # ============ 主入口 ============

    def consolidate_after_session(
        self,
        user_id: str,
        task_id: int,
        memory_group: str
    ) -> Dict:
        """
        Session 结束后的记忆固化

        Args:
            user_id: 用户ID
            task_id: 刚结束的任务ID
            memory_group: 记忆组别

        Returns:
            固化结果统计
        """
        stats = {
            'user_id': user_id,
            'task_id': task_id,
            'memory_group': memory_group,
            'timestamp': datetime.utcnow().isoformat(),
            'success': False,  # 默认失败，成功后改为 True
            'action': 'no_action',
            'error': None,
            'error_type': None
        }

        try:
            if memory_group == 'gist_memory':
                # L3: 用户画像增量更新
                print(f"[Consolidation] 开始 L3 固化: user={user_id}, task={task_id}")
                result = self._consolidate_gist(user_id, task_id)
                stats.update(result)

            elif memory_group == 'hybrid_memory':
                # L4: 批量向量生成
                print(f"[Consolidation] 开始 L4 固化: user={user_id}, task={task_id}")
                result = self._consolidate_vectors(user_id, task_id)
                stats.update(result)

            else:
                # L1, L2 不需要固化
                stats['action'] = 'no_consolidation_needed'

            stats['success'] = True
            print(f"[Consolidation] 固化成功: {stats}")

        except Exception as e:
            # 详细错误记录
            stats['success'] = False
            stats['error'] = str(e)
            stats['error_type'] = type(e).__name__

            # 错误分类
            if 'API' in str(e) or 'timeout' in str(e).lower():
                stats['error_category'] = 'api_failure'
            elif 'JSON' in str(e) or 'json' in str(e).lower():
                stats['error_category'] = 'llm_output_parsing_error'
            elif 'database' in str(e).lower() or 'sql' in str(e).lower():
                stats['error_category'] = 'database_error'
            else:
                stats['error_category'] = 'unknown_error'

            # 打印详细错误信息
            print(f"[Consolidation] ❌ 固化失败: {stats['error_category']}")
            print(f"[Consolidation] 错误详情: {e}")
            import traceback
            traceback.print_exc()

            # 记录到数据库（即使固化失败，也要记录日志）
            try:
                self.db.log_event(
                    user_id,
                    'consolidation_failed',
                    task_id=task_id,
                    event_data={
                        'error': str(e),
                        'error_type': stats['error_type'],
                        'error_category': stats['error_category'],
                        'memory_group': memory_group
                    }
                )
            except:
                # 如果连日志都记不了，至少打印出来
                print(f"[Consolidation] ⚠️ 无法记录失败日志")

        return stats

    # ============ L3: 用户画像增量固化 ============

    def _consolidate_gist(self, user_id: str, task_id: int) -> Dict:
        """
        L3 固化：提取用户画像增量并更新

        理论依据：Fuzzy Trace Theory
        - 保留语义本质（gist）
        - 丢弃字面细节（verbatim）

        实现：
        1. 读取本次 session 的所有对话
        2. 调用 LLM 提取用户特质
        3. 与已有画像合并
        4. 更新数据库
        """
        print(f"[Consolidation L3] 开始固化用户画像: user={user_id}, task={task_id}")

        # 1. 获取本次 session 的消息
        messages = self.db.get_task_messages(user_id, task_id)

        if not messages:
            return {'action': 'skip', 'reason': 'no_messages'}

        # 2. 构建对话文本
        conversation_text = self._format_messages_for_extraction(messages)

        # 3. 获取已有画像
        existing_profile = self._get_user_profile(user_id)

        # 4. 调用 LLM 提取增量画像
        if self.llm and hasattr(self.llm, 'chat_completion'):
            profile_increment = self._extract_profile_increment(
                conversation_text,
                existing_profile,
                task_id  # 传入任务ID用于溯源标注
            )
        else:
            # 降级方案：规则提取
            profile_increment = self._extract_profile_by_rules(conversation_text, task_id)

        # 5. 合并画像
        updated_profile = self._merge_profiles(existing_profile, profile_increment)

        # 6. 保存到数据库
        self._save_user_profile(user_id, updated_profile, task_id)

        return {
            'action': 'gist_consolidated',
            'messages_processed': len(messages),
            'profile_fields_updated': len(profile_increment.keys()),
            'new_traits_count': sum(len(v) for v in profile_increment.values() if isinstance(v, list))
        }

    def _extract_profile_increment(
        self,
        conversation: str,
        existing_profile: Dict,
        task_id: int
    ) -> Dict:
        """
        使用 LLM 提取用户画像增量（L3 增强版：含情感显著性）

        提示词设计（融合CHI'24 Hou et al.的情感显著性）：
        - 只提取**新增**的特质（避免重复）
        - 分类存储（基本信息、偏好、限制、目标等）
        - 🔴 新增：情感显著性提取（深层情感需求、核心价值观、高情感强度事件）
        """
        # 尝试从 config.py 读取增强版提示词
        enhanced_prompt_template = Config.GIST_CONFIG.get('profile_extraction_prompt', None)

        if enhanced_prompt_template:
            # 使用增强版提示词
            prompt = enhanced_prompt_template.format(
                existing_profile=json.dumps(existing_profile, ensure_ascii=False, indent=2),
                task_id=task_id,
                conversation=conversation
            )
        else:
            # 降级：使用内置的增强版提示词
            prompt = f"""你是一个用户画像分析助手。请根据以下对话，提取用户的长期特质。

**已知画像**：
{json.dumps(existing_profile, ensure_ascii=False, indent=2)}

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
"""

        try:
            # 调用 LLM（增加超时控制）
            response = self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 低温度保证输出稳定
                max_tokens=800
            )

            # 清理响应（移除可能的 markdown 代码块标记）
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # 解析 JSON
            profile_increment = json.loads(cleaned_response)

            # 验证格式
            if not isinstance(profile_increment, dict):
                print(f"[Consolidation] ⚠️ LLM 返回非字典格式，使用空画像")
                return {}

            return profile_increment

        except json.JSONDecodeError as e:
            print(f"[Consolidation] ❌ LLM 返回 JSON 格式错误: {e}")
            print(f"[Consolidation] 原始输出（前 500 字符）:")
            print(response[:500] if 'response' in locals() else "无响应")
            return {}

        except TimeoutError:
            print(f"[Consolidation] ❌ LLM 调用超时")
            return {}

        except Exception as e:
            print(f"[Consolidation] ❌ LLM 调用失败: {type(e).__name__}: {e}")
            return {}

    def _extract_profile_by_rules(self, conversation: str, task_id: int) -> Dict:
        """
        降级方案：基于规则的画像提取（当 LLM 不可用时）

        使用简单的关键词匹配
        """
        profile = {
            "preferences": [],
            "constraints": [],
            "goals": []
        }

        # 偏好关键词
        preference_patterns = [
            ("喜欢", "preferences"),
            ("爱好", "preferences"),
            ("最爱", "preferences"),
            ("不喜欢", "constraints"),
            ("讨厌", "constraints"),
            ("过敏", "constraints"),
            ("想要", "goals"),
            ("打算", "goals"),
            ("计划", "goals")
        ]

        lines = conversation.split('\n')
        for line in lines:
            if line.startswith('用户：'):
                content = line[3:].strip()

                for pattern, category in preference_patterns:
                    if pattern in content:
                        # 简单提取（实际应该用 NER）
                        trait = content[:50]  # 截取前 50 字
                        # 添加溯源标注
                        trait_with_source = f"{trait} [Task {task_id}]"
                        if trait and trait_with_source not in profile[category]:
                            profile[category].append(trait_with_source)

        return profile

    def _merge_profiles(self, existing: Dict, increment: Dict) -> Dict:
        """
        合并已有画像和增量画像

        策略：
        - 字典类型：更新键值
        - 列表类型：去重追加
        """
        merged = existing.copy()

        for key, value in increment.items():
            if key not in merged:
                merged[key] = value
            else:
                if isinstance(value, dict):
                    # 合并字典
                    merged[key].update(value)
                elif isinstance(value, list):
                    # 去重追加列表
                    existing_set = set(merged[key])
                    for item in value:
                        if item not in existing_set:
                            merged[key].append(item)

        return merged

    def _get_user_profile(self, user_id: str) -> Dict:
        """获取用户现有画像"""
        return self.db.get_user_profile(user_id)

    def _save_user_profile(self, user_id: str, profile: Dict, task_id: int):
        """保存用户画像"""
        print(f"[Consolidation] 画像已更新:")
        print(json.dumps(profile, ensure_ascii=False, indent=2))

        # 保存到数据库
        self.db.save_user_profile(user_id, profile, task_id)

    def _format_messages_for_extraction(self, messages) -> str:
        """格式化消息用于画像提取"""
        lines = []
        for msg in messages:
            role = "用户" if msg.is_user else "AI"
            lines.append(f"{role}：{msg.content}")
        return "\n".join(lines)

    # ============ L4: 向量批量固化 ============

    def _consolidate_vectors(self, user_id: str, task_id: int) -> Dict:
        """
        L4 固化：批量生成向量并存储

        理论依据：Tulving 陈述性记忆
        - 向量化后的记忆支持语义检索

        实现：
        1. 找到本次 session 中未向量化的消息
        2. 批量调用 DashScope Embedding API
        3. 更新 chat_messages.embedding 字段
        """
        print(f"[Consolidation L4] 开始批量向量化: user={user_id}, task={task_id}")

        # 1. 获取未向量化的消息
        messages = self.db.get_task_messages(user_id, task_id)

        if not messages:
            return {'action': 'skip', 'reason': 'no_messages'}

        # 过滤出未向量化的消息
        unvectorized = [msg for msg in messages if not msg.embedding]

        if not unvectorized:
            return {
                'action': 'vectors_already_exist',
                'total_messages': len(messages)
            }

        # 2. 批量生成向量
        texts = [msg.content for msg in unvectorized]
        embeddings = self.vector_store.generate_embeddings_batch(texts)

        # 3. 更新数据库（含情感显著性）
        success_count = 0
        fail_count = 0

        for msg, embedding in zip(unvectorized, embeddings):
            if embedding:
                # 计算重要性分数（简单规则）
                importance = self._calculate_importance(msg.content, msg.is_user)

                # 🔴 计算情感显著性（使用混合方法）
                # 根据config配置选择方法：'rule', 'llm', 'hybrid'
                config = Config.EXPERIMENT_CONFIG.get('emotional_salience', {})
                method = config.get('method', 'hybrid')

                if method == 'llm':
                    # 纯LLM方法
                    emotional_salience = self._calculate_emotional_salience_llm(msg.content, msg.is_user)
                elif method == 'hybrid':
                    # 混合方法（推荐）
                    emotional_salience = self._calculate_emotional_salience_hybrid(msg.content, msg.is_user)
                else:
                    # 默认规则方法
                    emotional_salience = self._calculate_emotional_salience(msg.content, msg.is_user)

                # 更新数据库
                if self._update_message_with_embedding_and_salience(
                    msg.message_id,
                    embedding,
                    importance,
                    emotional_salience
                ):
                    success_count += 1
                else:
                    fail_count += 1
            else:
                fail_count += 1

        return {
            'action': 'vectors_consolidated',
            'total_messages': len(messages),
            'unvectorized_before': len(unvectorized),
            'success': success_count,
            'failed': fail_count
        }

    def _update_message_with_embedding_and_salience(
        self,
        message_id: str,
        embedding: list,
        importance_score: float,
        emotional_salience: float
    ) -> bool:
        """
        更新消息的向量、重要性和情感显著性

        Args:
            message_id: 消息ID
            embedding: 向量
            importance_score: 重要性分数
            emotional_salience: 情感显著性分数

        Returns:
            是否成功
        """
        from database import ChatMessage

        try:
            msg = self.db.session.query(ChatMessage).filter(
                ChatMessage.message_id == message_id
            ).first()

            if msg:
                msg.embedding = json.dumps(embedding)
                msg.importance_score = importance_score
                # 更新情感显著性字段
                if hasattr(msg, 'emotional_salience'):
                    msg.emotional_salience = emotional_salience

                # 🔴 双层机制 - 固化层：情感影响初始固化系数
                # 公式：g_0 = 3.0 + 1.5 * emotional_salience
                # 无情感(e=0): g_0=3.0，覆盖2天间隔（周一→周三）
                # 高情感(e=1): g_0=4.5，覆盖3天间隔（周五→下周一）
                if hasattr(msg, 'consolidation_g'):
                    initial_g = 3.0 + 1.5 * emotional_salience
                    msg.consolidation_g = initial_g

                self.db.session.commit()
                return True

            return False

        except Exception as e:
            print(f"[Consolidation] 更新消息失败: {e}")
            self.db.session.rollback()
            return False

    def _calculate_importance(self, content: str, is_user: bool) -> float:
        """
        计算消息的重要性分数

        简单规则（可以改为 LLM 判断）：
        - 用户的自我披露：高重要性
        - 包含关键词（姓名、情感、决策）：高重要性
        - AI 的回复：中等重要性
        """
        importance = 0.5  # 基础分

        if is_user:
            importance += 0.2  # 用户消息更重要

            # 关键词匹配
            high_importance_keywords = [
                '我是', '我叫', '我的', '我觉得', '我认为', '我决定',
                '喜欢', '讨厌', '希望', '担心', '害怕', '开心', '难过'
            ]

            if any(kw in content for kw in high_importance_keywords):
                importance += 0.2

            # 长消息更可能包含重要信息
            if len(content) > 50:
                importance += 0.1

        # 限制在 0-1 范围
        return min(1.0, importance)

    def _calculate_emotional_salience(self, content: str, is_user: bool) -> float:
        """
        计算消息的情感显著性分数（基于规则的快速方法）

        情感显著性反映消息的情感强度和深度，用于：
        1. L3 画像提取时识别高情感强度事件
        2. L4 向量检索时提升情感相关记忆的权重

        规则：
        - 高情感强度词汇：+0.3
        - 自我披露词汇：+0.2
        - 价值观相关词汇：+0.1

        Returns:
            情感显著性分数 0-1
        """
        salience = 0.0

        if not is_user:
            return 0.0  # AI消息的情感显著性为0

        # 高情感强度词汇
        high_emotion_keywords = [
            # 喜
            '太开心了', '太高兴了', '兴奋', '激动', '感动', '幸福', '满足',
            # 怒
            '生气', '愤怒', '气死', '烦死', '讨厌', '受不了',
            # 哀
            '难过', '伤心', '失落', '沮丧', '绝望', '心痛', '想哭', '崩溃',
            # 惧
            '害怕', '恐惧', '担心', '焦虑', '紧张', '不安', '压力',
            # 期待
            '期待', '盼望', '希望', '想要', '梦想',
            # 失望
            '失望', '遗憾', '可惜', '后悔'
        ]

        # 自我披露词汇
        self_disclosure_keywords = [
            '其实我', '说实话', '老实说', '跟你说', '告诉你',
            '从来没', '第一次', '一直以来', '内心', '真正的我'
        ]

        # 价值观相关词汇
        value_keywords = [
            '最重要', '最在乎', '一定要', '绝对不', '原则', '底线',
            '意义', '价值', '人生', '理想', '信念'
        ]

        # 计算分数
        if any(kw in content for kw in high_emotion_keywords):
            salience += 0.3

        if any(kw in content for kw in self_disclosure_keywords):
            salience += 0.2

        if any(kw in content for kw in value_keywords):
            salience += 0.1

        # 感叹号和问号也可能表示情感强度
        exclamation_count = content.count('！') + content.count('!')
        question_count = content.count('？') + content.count('?')
        if exclamation_count >= 2:
            salience += 0.1
        if question_count >= 2:
            salience += 0.05

        # 限制在 0-1 范围
        return min(1.0, salience)

    def _calculate_emotional_salience_llm(self, content: str, is_user: bool) -> float:
        """
        使用LLM评估情感显著性（精确版）

        评估维度：
        1. 情感强度 (Emotional Intensity): 0-1
        2. 自我披露深度 (Self-Disclosure Depth): 0-1
        3. 价值观相关性 (Value Relevance): 0-1

        Args:
            content: 消息内容
            is_user: 是否为用户消息

        Returns:
            情感显著性分数 0-1
        """
        if not is_user:
            return 0.0  # AI消息不计算

        if not self.llm or not hasattr(self.llm, 'generate_response'):
            # LLM不可用，返回中性值 0.0（不施加情感加成，避免引入量纲不一致的规则法分数）
            print(f"[情感打分] LLM不可用，返回 0.0")
            return 0.0

        # 读取配置权重
        weights = Config.EXPERIMENT_CONFIG.get('emotional_salience', {}).get('weights', {
            'emotional_intensity': 0.4,
            'self_disclosure_depth': 0.4,
            'value_relevance': 0.2
        })

        # 构建提示词
        prompt = f"""请评估以下用户消息的情感显著性。

**用户消息**: "{content}"

**评估维度**（每个维度0-1分）：
1. **情感强度** (Emotional Intensity): 消息中表达的情感有多强烈？
   - 0.0分: 无情感（如"今天天气不错"）
   - 0.3分: 轻微情感（如"有点开心"）
   - 0.7分: 中等情感（如"很高兴"）
   - 1.0分: 极强情感（如"太激动了！简直不敢相信！"、"我崩溃了"）

2. **自我披露深度** (Self-Disclosure Depth): 用户是否分享了私密/深层信息？
   - 0.0分: 客观事实（如"我住在北京"）
   - 0.3分: 浅层偏好（如"我喜欢咖啡"）
   - 0.7分: 深层想法（如"其实我一直很焦虑"）
   - 1.0分: 核心隐私（如"我从没告诉过别人..."）

3. **价值观相关性** (Value Relevance): 是否涉及用户的核心价值观或人生原则？
   - 0.0分: 无关（如"今天吃了面条"）
   - 0.3分: 轻微相关（如"我比较注重健康"）
   - 0.7分: 中度相关（如"家人对我很重要"）
   - 1.0分: 核心价值观（如"我人生最重要的原则是..."）

**输出格式**（仅输出JSON，不要任何解释）：
{{
  "emotional_intensity": 0.0,
  "self_disclosure_depth": 0.0,
  "value_relevance": 0.0
}}

如果消息为空或无法评估，返回 {{"emotional_intensity": 0.0, "self_disclosure_depth": 0.0, "value_relevance": 0.0}}
"""

        try:
            # 调用LLM
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # 低温度保证稳定性
                max_tokens=150
            )

            # 清理响应（移除可能的markdown代码块）
            cleaned = response.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # 解析JSON
            scores = json.loads(cleaned)

            # 验证分数范围
            for key in ['emotional_intensity', 'self_disclosure_depth', 'value_relevance']:
                if key in scores:
                    scores[key] = max(0.0, min(1.0, scores[key]))

            # 计算加权平均
            emotional_salience = (
                scores.get('emotional_intensity', 0.0) * weights.get('emotional_intensity', 0.4) +
                scores.get('self_disclosure_depth', 0.0) * weights.get('self_disclosure_depth', 0.4) +
                scores.get('value_relevance', 0.0) * weights.get('value_relevance', 0.2)
            )

            # 限制在 [0, 1]
            emotional_salience = max(0.0, min(1.0, emotional_salience))

            print(f"[LLM情感打分] 消息: {content[:30]}... → {emotional_salience:.3f}")
            print(f"  详细: intensity={scores.get('emotional_intensity', 0):.2f}, "
                  f"disclosure={scores.get('self_disclosure_depth', 0):.2f}, "
                  f"value={scores.get('value_relevance', 0):.2f}")

            return emotional_salience

        except json.JSONDecodeError as e:
            print(f"[情感打分] JSON解析失败: {e}")
            print(f"  原始输出: {response[:200] if 'response' in locals() else 'N/A'}")
            return 0.0

        except Exception as e:
            print(f"[情感打分] LLM调用失败: {type(e).__name__}: {e}")
            return 0.0

    def _calculate_emotional_salience_hybrid(
        self,
        content: str,
        is_user: bool
    ) -> float:
        """
        混合方法：规则快速筛选 + LLM精确打分

        流程：
        1. 第一层：规则方法快速评估
        2. 如果分数低于阈值 → 直接返回（节省API）
        3. 如果分数高于阈值 → 调用LLM精确打分

        Args:
            content: 消息内容
            is_user: 是否为用户消息

        Returns:
            情感显著性分数 0-1
        """
        if not is_user:
            return 0.0

        # 读取配置
        config = Config.EXPERIMENT_CONFIG.get('emotional_salience', {})
        method = config.get('method', 'hybrid')
        llm_threshold = config.get('llm_threshold', 0.2)
        enable_llm = config.get('enable_llm', True)

        # 🔴 第一层：规则快速筛选
        rule_score = self._calculate_emotional_salience(content, is_user)

        # 如果禁用LLM或分数很低，直接返回
        if not enable_llm or rule_score < llm_threshold:
            print(f"[混合打分] 规则分数{rule_score:.2f} < 阈值{llm_threshold}，跳过LLM")
            return rule_score

        # 🔴 第二层：LLM精确打分
        print(f"[混合打分] 规则分数{rule_score:.2f} >= 阈值{llm_threshold}，调用LLM精确评估")
        llm_score = self._calculate_emotional_salience_llm(content, is_user)

        # 返回LLM分数（更准确）
        return llm_score

    # ============ 工具方法 ============

    def get_consolidation_stats(self, user_id: str) -> Dict:
        """获取固化统计信息"""
        stats = {
            'user_id': user_id
        }

        # L3 画像统计
        profile = self._get_user_profile(user_id)
        stats['profile_traits_count'] = sum(
            len(v) if isinstance(v, list) else 1
            for v in profile.values()
        )

        # L4 向量统计
        vector_stats = self.vector_store.get_stats(user_id)
        stats.update(vector_stats)

        return stats
