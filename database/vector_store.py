"""
向量存储层 (Vector Store) - Numpy 版

使用 Numpy + SQLite 实现 L4 混合记忆检索

功能：
- DashScope Embedding API (通义千问 text-embedding-v3)
- 向量存入 SQLite chat_messages.embedding 字段
- Numpy 余弦相似度计算
- 动态遗忘曲线检索（基于CHI'24 Hou et al.）：
  公式: p_n(t) = [1 - exp(-r·e^{-t/g_n})] / (1 - e^{-1})
  固化更新: g_n = g_{n-1} + S(t), S(t) = (1-e^{-t})/(1+e^{-t})
"""

import json
import math
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from config import Config


@dataclass
class MemoryItem:
    """检索结果条目（L4 动态遗忘曲线增强版）"""
    message_id: str
    user_id: str
    task_id: int
    content: str
    timestamp: datetime
    is_user: bool
    importance_score: float
    similarity_score: float = 0.0
    recency_score: float = 0.0
    final_score: float = 0.0
    # 动态遗忘曲线字段
    consolidation_g: float = 1.0       # 固化系数 g_n
    recall_count: int = 0              # 召回次数 n
    recall_probability: float = 0.0    # 召回概率 p(t)
    days_since_last_recall: float = 0.0  # 距上次召回天数
    # 情感显著性字段（CHI'24 增强）
    emotional_salience: float = 0.0    # 情感显著性分数

    def to_dict(self) -> Dict:
        return {
            'message_id': self.message_id,
            'user_id': self.user_id,
            'task_id': self.task_id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_user': self.is_user,
            'importance_score': round(self.importance_score, 3),
            'similarity_score': round(self.similarity_score, 3),
            'recency_score': round(self.recency_score, 3),
            'final_score': round(self.final_score, 3),
            # 动态遗忘曲线字段
            'consolidation_g': round(self.consolidation_g, 3),
            'recall_count': self.recall_count,
            'recall_probability': round(self.recall_probability, 3),
            'days_since_last_recall': round(self.days_since_last_recall, 2),
            # 情感显著性字段
            'emotional_salience': round(self.emotional_salience, 3),
        }


class DynamicMemoryRecall:
    """
    动态记忆召回模型（基于CHI'24 Hou et al.）

    核心公式：
    - 召回概率: p_n(t) = [1 - exp(-r · e^{-t/g_n})] / (1 - e^{-1})
    - 固化更新: g_n = g_{n-1} + S(t), S(t) = (1-e^{-t})/(1+e^{-t})

    其中:
    - r = 语义相似度 (cosine similarity, 0-1)
    - t = 距上次召回的时间间隔（天）
    - g_n = 累积固化强度（召回次数越多，g越大，衰减越慢）
    """

    def __init__(
        self,
        initial_g: float = 1.0,
        recall_threshold: float = 0.86,
        time_unit: str = 'days'
    ):
        """
        初始化动态记忆召回模型

        Args:
            initial_g: 初始固化系数 g_0 (默认 1.0)
            recall_threshold: 召回概率阈值 k (默认 0.86，CHI论文建议值)
            time_unit: 时间单位 ('days', 'hours', 'seconds')
        """
        self.initial_g = initial_g
        self.recall_threshold = recall_threshold
        self.time_unit = time_unit

    def calculate_recall_probability(
        self,
        relevance: float,
        elapsed_time: float,
        consolidation_g: float = None
    ) -> float:
        """
        计算召回概率（CHI论文公式8）

        p_n(t) = [1 - exp(-r · e^{-t/g_n})] / (1 - e^{-1})

        Args:
            relevance: r - 语义相似度 (0-1)
            elapsed_time: t - 距上次召回的时间（单位由time_unit决定）
            consolidation_g: g_n - 当前固化系数

        Returns:
            召回概率 (0-1)
        """
        if consolidation_g is None or consolidation_g <= 0:
            consolidation_g = self.initial_g

        # 避免除零
        if consolidation_g == 0:
            consolidation_g = 0.001

        # 指数衰减项: e^{-t/g_n}
        decay_term = math.exp(-elapsed_time / consolidation_g)

        # 召回概率分子: 1 - exp(-r · decay_term)
        numerator = 1 - math.exp(-relevance * decay_term)

        # 归一化分母: 1 - e^{-1} ≈ 0.632
        denominator = 1 - math.exp(-1)

        probability = numerator / denominator

        # 确保在 [0, 1] 范围内
        return max(0.0, min(1.0, probability))

    def update_consolidation(
        self,
        current_g: float,
        recall_interval: float
    ) -> float:
        """
        更新固化系数（CHI论文公式9）

        g_n = g_{n-1} + S(t)
        S(t) = (1 - e^{-t}) / (1 + e^{-t})  (修正sigmoid)

        召回间隔越长，S(t)越大，固化强度增加越多
        这模拟了"间隔效应"：间隔较长的重复比间隔较短的重复更有效

        Args:
            current_g: 当前固化系数 g_{n-1}
            recall_interval: 距上次召回的时间间隔

        Returns:
            更新后的固化系数 g_n
        """
        t = max(0.001, recall_interval)  # 避免 t=0

        # 修正sigmoid: S(t) = (1 - e^{-t}) / (1 + e^{-t})
        # 当 t → 0: S(t) → 0
        # 当 t → ∞: S(t) → 1
        s_t = (1 - math.exp(-t)) / (1 + math.exp(-t))

        return current_g + s_t

    def should_recall(self, probability: float) -> bool:
        """
        判断是否应该触发召回

        Args:
            probability: 召回概率

        Returns:
            是否超过阈值
        """
        return probability >= self.recall_threshold

    def calculate_elapsed_days(
        self,
        last_recall_at: datetime,
        current_time: datetime = None
    ) -> float:
        """
        计算距上次召回的天数

        Args:
            last_recall_at: 上次召回时间
            current_time: 当前时间（默认 now）

        Returns:
            天数（浮点数）
        """
        if current_time is None:
            current_time = datetime.utcnow()

        if last_recall_at is None:
            # 如果从未被召回，使用消息创建时间
            return 1.0  # 默认1天

        delta = current_time - last_recall_at

        if self.time_unit == 'days':
            return delta.total_seconds() / 86400.0
        elif self.time_unit == 'hours':
            return delta.total_seconds() / 3600.0
        else:
            return delta.total_seconds()


class DashScopeEmbedding:
    """通义千问 text-embedding-v3 API"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.EXPERIMENT_CONFIG.get('qwen_api_key')
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        self.model = "text-embedding-v3"
        self.dimension = 1024

    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量生成向量"""
        if not texts:
            return []

        results = []
        batch_size = 10  # API 限制: text-embedding-v3 最大 10 条

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = self._call_api(batch)
            results.extend(batch_results)

        return results

    def embed_single(self, text: str) -> Optional[List[float]]:
        """生成单个向量"""
        if not text or not text.strip():
            return None
        results = self._call_api([text])
        return results[0] if results else None

    def _call_api(self, texts: List[str], verbose: bool = False) -> List[Optional[List[float]]]:
        """调用 API"""
        try:
            if verbose:
                print(f"[Embedding] 调用 API:")
                print(f"    URL: {self.base_url}")
                print(f"    Model: {self.model}")
                print(f"    API Key: {self.api_key[:10]}...{self.api_key[-4:] if len(self.api_key) > 14 else ''}")
                print(f"    Texts: {len(texts)} 条")

            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": {"texts": texts},
                    "parameters": {"text_type": "document", "dimension": self.dimension}
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'output' in data and 'embeddings' in data['output']:
                    sorted_emb = sorted(data['output']['embeddings'], key=lambda x: x['text_index'])
                    return [item['embedding'] for item in sorted_emb]

            # 打印详细错误信息
            print(f"[Embedding] API 错误: HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"[Embedding] 错误详情:")
                print(f"    code: {error_data.get('code', 'N/A')}")
                print(f"    message: {error_data.get('message', 'N/A')}")
                print(f"    request_id: {error_data.get('request_id', 'N/A')}")
            except:
                print(f"[Embedding] 响应内容: {response.text[:500]}")

            return [None] * len(texts)

        except Exception as e:
            print(f"[Embedding] 请求失败: {e}")
            return [None] * len(texts)

    def test_single(self, text: str = "这是一条测试消息") -> bool:
        """测试单条消息向量化"""
        print("\n" + "=" * 50)
        print("Embedding API 单条测试")
        print("=" * 50)
        print(f"测试文本: {text}")
        print()

        result = self._call_api([text], verbose=True)

        if result and result[0]:
            print(f"\n[OK] 成功! 向量维度: {len(result[0])}")
            print(f"     向量前5个值: {result[0][:5]}")
            return True
        else:
            print(f"\n[FAIL] 失败!")
            return False


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算余弦相似度

    Returns:
        相似度 0-1 (已归一化)
    """
    if not vec1 or not vec2:
        return 0.0

    a = np.array(vec1, dtype=np.float32)
    b = np.array(vec2, dtype=np.float32)

    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    # 余弦相似度 [-1, 1] → 归一化到 [0, 1]
    sim = dot / (norm_a * norm_b)
    return float((sim + 1) / 2)


class VectorStore:
    """
    向量存储管理器（L4 动态遗忘曲线增强版）

    检索策略:
    1. 旧版静态加权: Score = α·Recency + β·Similarity + γ·Importance
    2. 新版动态遗忘曲线（CHI'24）: p_n(t) = [1-exp(-r·e^{-t/g_n})]/(1-e^{-1})

    使用动态遗忘曲线时:
    - 概率阈值触发召回（而非简单Top-K）
    - 召回后更新固化系数（越回忆越牢固）
    """

    # 从 config.py 读取权重
    WEIGHTS = Config.MEMORY_OPERATIONS.get('hybrid_memory', {
        'alpha': 0.3,
        'beta': 0.5,
        'gamma': 0.2
    })

    # 从 config.py 读取遗忘曲线配置
    FORGETTING_CURVE_CONFIG = Config.EXPERIMENT_CONFIG.get('memory_config', {}).get(
        'hybrid_memory', {}
    ).get('forgetting_curve', {
        'enabled': True,
        'initial_g': 1.0,
        'recall_threshold': 0.86,
        'time_unit': 'days',
        'update_on_recall': True
    })

    def __init__(self, db_manager=None):
        """
        初始化

        Args:
            db_manager: DBManager 实例（用于数据库操作）
        """
        self.db = db_manager
        self.embedding_fn = DashScopeEmbedding()

        # 初始化动态记忆召回模型
        self.recall_model = DynamicMemoryRecall(
            initial_g=self.FORGETTING_CURVE_CONFIG.get('initial_g', 1.0),
            recall_threshold=self.FORGETTING_CURVE_CONFIG.get('recall_threshold', 0.86),
            time_unit=self.FORGETTING_CURVE_CONFIG.get('time_unit', 'days')
        )

    def set_db_manager(self, db_manager):
        """设置数据库管理器"""
        self.db = db_manager

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """生成单条文本的向量"""
        return self.embedding_fn.embed_single(text)

    def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量生成向量"""
        return self.embedding_fn.embed_texts(texts)

    def search_weighted(
        self,
        user_id: str,
        query: str,
        exclude_task_id: int = None,
        top_k: int = 3,
        alpha: float = None,
        beta: float = None,
        gamma: float = None
    ) -> List[MemoryItem]:
        """
        加权向量检索

        Score = α·Recency + β·Similarity + γ·Importance

        Args:
            user_id: 用户ID
            query: 查询文本
            exclude_task_id: 排除的任务ID（当前任务）
            top_k: 返回数量
            alpha: 新鲜度权重 (默认 0.3)
            beta: 相似度权重 (默认 0.5)
            gamma: 重要性权重 (默认 0.2)

        Returns:
            排序后的记忆列表
        """
        if not self.db:
            print("[VectorStore] 数据库未初始化")
            return []

        # 使用配置权重
        alpha = alpha if alpha is not None else self.WEIGHTS['alpha']
        beta = beta if beta is not None else self.WEIGHTS['beta']
        gamma = gamma if gamma is not None else self.WEIGHTS['gamma']

        # 1. 生成查询向量
        query_embedding = self.embedding_fn.embed_single(query)
        if not query_embedding:
            print("[VectorStore] 查询向量生成失败")
            return []

        # 2. 获取用户所有有向量的历史消息
        messages = self._get_user_messages_with_embedding(user_id, exclude_task_id)
        if not messages:
            return []

        # 3. 计算时间范围（用于新鲜度归一化）
        timestamps = [m['timestamp'] for m in messages]
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        time_range = (max_ts - min_ts).total_seconds() or 1

        # 4. 计算每条消息的加权分数
        results = []
        for msg in messages:
            # β: 相似度
            similarity = cosine_similarity(query_embedding, msg['embedding'])

            # α: 新鲜度 (0=最旧, 1=最新)
            recency = (msg['timestamp'] - min_ts).total_seconds() / time_range

            # γ: 重要性
            importance = msg.get('importance_score', 0.5)

            # 加权公式
            final_score = alpha * recency + beta * similarity + gamma * importance

            results.append(MemoryItem(
                message_id=msg['message_id'],
                user_id=msg['user_id'],
                task_id=msg['task_id'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                is_user=msg['is_user'],
                importance_score=importance,
                similarity_score=similarity,
                recency_score=recency,
                final_score=final_score
            ))

        # 5. 按分数排序，取 Top-K
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]

    def search_with_forgetting_curve(
        self,
        user_id: str,
        query: str,
        exclude_task_id: int = None,
        top_k: int = 5,
        update_on_recall: bool = True
    ) -> List[MemoryItem]:
        """
        动态遗忘曲线检索（CHI'24 Hou et al.）

        核心公式:
        - 召回概率: p_n(t) = [1 - exp(-r · e^{-t/g_n})] / (1 - e^{-1})
        - 固化更新: g_n = g_{n-1} + S(t)

        Args:
            user_id: 用户ID
            query: 查询文本
            exclude_task_id: 排除的任务ID（当前任务）
            top_k: 最大返回数量（在阈值筛选后）
            update_on_recall: 是否在召回后更新固化系数

        Returns:
            符合召回阈值的记忆列表（按召回概率排序）
        """
        if not self.db:
            print("[VectorStore] 数据库未初始化")
            return []

        # 1. 生成查询向量
        query_embedding = self.embedding_fn.embed_single(query)
        if not query_embedding:
            print("[VectorStore] 查询向量生成失败，降级为静态检索")
            return self.search_weighted(user_id, query, exclude_task_id, top_k)

        # 2. 获取用户所有有向量的历史消息（含动态字段）
        messages = self._get_user_messages_with_dynamic_fields(user_id, exclude_task_id)
        if not messages:
            return []

        current_time = datetime.utcnow()
        recalled_memories = []
        recall_model = self.recall_model

        # 3. 计算每条消息的召回概率（融合情感显著性）
        for msg in messages:
            # 语义相似度 r
            similarity = cosine_similarity(query_embedding, msg['embedding'])

            # 距上次召回的时间 t（天）
            last_recall = msg.get('last_recall_at') or msg['timestamp']
            elapsed_days = recall_model.calculate_elapsed_days(last_recall, current_time)

            # 固化系数 g_n
            consolidation_g = msg.get('consolidation_g', 1.0)

            # 🔴 情感显著性 (CHI'24 增强)
            emotional_salience = msg.get('emotional_salience', 0.0)

            # 计算基础召回概率
            base_recall_prob = recall_model.calculate_recall_probability(
                relevance=similarity,
                elapsed_time=elapsed_days,
                consolidation_g=consolidation_g
            )

            # 🔴 情感显著性加成：高情感显著性的记忆更容易被召回
            # 公式: final_prob = base_prob + emotional_bonus
            # emotional_bonus = emotional_salience * 0.1 (最多提升0.1)
            emotional_bonus = emotional_salience * 0.1
            recall_prob = min(1.0, base_recall_prob + emotional_bonus)

            # 创建 MemoryItem
            memory = MemoryItem(
                message_id=msg['message_id'],
                user_id=msg['user_id'],
                task_id=msg['task_id'],
                content=msg['content'],
                timestamp=msg['timestamp'],
                is_user=msg['is_user'],
                importance_score=msg.get('importance_score', 0.5),
                similarity_score=similarity,
                consolidation_g=consolidation_g,
                recall_count=msg.get('recall_count', 0),
                recall_probability=recall_prob,
                days_since_last_recall=elapsed_days,
                final_score=recall_prob,  # 使用召回概率作为最终分数
                emotional_salience=emotional_salience  # 🔴 情感显著性
            )

            # 4. 阈值筛选：只有超过阈值的才被召回
            if recall_model.should_recall(recall_prob):
                recalled_memories.append(memory)

                # 5. 更新固化系数（被召回后变得更难遗忘）
                if update_on_recall and self.FORGETTING_CURVE_CONFIG.get('update_on_recall', True):
                    new_g = recall_model.update_consolidation(consolidation_g, elapsed_days)
                    new_recall_count = msg.get('recall_count', 0) + 1

                    self._update_memory_dynamic_fields(
                        msg['message_id'],
                        consolidation_g=new_g,
                        recall_count=new_recall_count,
                        last_recall_at=current_time
                    )

        # 6. 按召回概率排序，取 Top-K
        recalled_memories.sort(key=lambda x: x.recall_probability, reverse=True)

        # 日志输出
        print(f"[VectorStore] 动态遗忘曲线检索: "
              f"候选={len(messages)}, 超阈值={len(recalled_memories)}, "
              f"阈值={recall_model.recall_threshold}")

        return recalled_memories[:top_k]

    def _get_user_messages_with_dynamic_fields(
        self,
        user_id: str,
        exclude_task_id: int = None
    ) -> List[Dict]:
        """
        获取用户所有有向量的消息（含动态遗忘曲线字段）

        Returns:
            消息列表，包含: embedding, consolidation_g, recall_count, last_recall_at
        """
        from database import ChatMessage

        try:
            query = self.db.session.query(ChatMessage).filter(
                ChatMessage.user_id == user_id,
                ChatMessage.embedding.isnot(None)
            )

            if exclude_task_id is not None:
                query = query.filter(ChatMessage.task_id != exclude_task_id)

            messages = query.all()

            result = []
            for msg in messages:
                try:
                    embedding = json.loads(msg.embedding) if msg.embedding else None
                except:
                    embedding = None

                if embedding:
                    result.append({
                        'message_id': msg.message_id,
                        'user_id': msg.user_id,
                        'task_id': msg.task_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp,
                        'is_user': msg.is_user,
                        'importance_score': msg.importance_score or 0.5,
                        'embedding': embedding,
                        # 动态遗忘曲线字段
                        'consolidation_g': getattr(msg, 'consolidation_g', None) or 1.0,
                        'recall_count': getattr(msg, 'recall_count', None) or 0,
                        'last_recall_at': getattr(msg, 'last_recall_at', None),
                        'emotional_salience': getattr(msg, 'emotional_salience', None) or 0.0
                    })

            return result

        except Exception as e:
            print(f"[VectorStore] 查询失败: {e}")
            return []

    def _update_memory_dynamic_fields(
        self,
        message_id: str,
        consolidation_g: float = None,
        recall_count: int = None,
        last_recall_at: datetime = None
    ) -> bool:
        """
        更新消息的动态遗忘曲线字段

        Args:
            message_id: 消息ID
            consolidation_g: 新的固化系数
            recall_count: 新的召回次数
            last_recall_at: 新的上次召回时间

        Returns:
            是否成功
        """
        from database import ChatMessage

        try:
            msg = self.db.session.query(ChatMessage).filter(
                ChatMessage.message_id == message_id
            ).first()

            if msg:
                if consolidation_g is not None:
                    msg.consolidation_g = consolidation_g
                if recall_count is not None:
                    msg.recall_count = recall_count
                if last_recall_at is not None:
                    msg.last_recall_at = last_recall_at

                self.db.session.commit()
                return True

            return False

        except Exception as e:
            print(f"[VectorStore] 更新动态字段失败: {e}")
            self.db.session.rollback()
            return False

    def _get_user_messages_with_embedding(
        self,
        user_id: str,
        exclude_task_id: int = None
    ) -> List[Dict]:
        """
        获取用户所有有向量的消息

        Args:
            user_id: 用户ID
            exclude_task_id: 排除的任务ID

        Returns:
            消息列表（包含解析后的向量）
        """
        from database import ChatMessage

        try:
            query = self.db.session.query(ChatMessage).filter(
                ChatMessage.user_id == user_id,
                ChatMessage.embedding.isnot(None)
            )

            if exclude_task_id is not None:
                query = query.filter(ChatMessage.task_id != exclude_task_id)

            messages = query.all()

            result = []
            for msg in messages:
                # 解析 JSON 格式的向量
                try:
                    embedding = json.loads(msg.embedding) if msg.embedding else None
                except:
                    embedding = None

                if embedding:
                    result.append({
                        'message_id': msg.message_id,
                        'user_id': msg.user_id,
                        'task_id': msg.task_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp,
                        'is_user': msg.is_user,
                        'importance_score': msg.importance_score or 0.5,
                        'embedding': embedding
                    })

            return result

        except Exception as e:
            print(f"[VectorStore] 查询失败: {e}")
            return []

    def update_message_embedding(
        self,
        message_id: str,
        embedding: List[float],
        importance_score: float = None
    ) -> bool:
        """
        更新消息的向量和重要性分数

        Args:
            message_id: 消息ID
            embedding: 向量
            importance_score: 重要性分数

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
                if importance_score is not None:
                    msg.importance_score = importance_score
                self.db.session.commit()
                return True

            return False

        except Exception as e:
            print(f"[VectorStore] 更新失败: {e}")
            self.db.session.rollback()
            return False

    def get_stats(self, user_id: str = None) -> Dict:
        """获取统计信息"""
        from database import ChatMessage

        try:
            query = self.db.session.query(ChatMessage)

            if user_id:
                query = query.filter(ChatMessage.user_id == user_id)

            total = query.count()
            with_embedding = query.filter(ChatMessage.embedding.isnot(None)).count()

            return {
                "total_messages": total,
                "with_embedding": with_embedding,
                "coverage": f"{with_embedding/total*100:.1f}%" if total > 0 else "0%"
            }

        except Exception as e:
            return {"error": str(e)}


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store(db_manager=None) -> VectorStore:
    """获取向量存储单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(db_manager)
    elif db_manager and _vector_store.db is None:
        _vector_store.set_db_manager(db_manager)
    return _vector_store
