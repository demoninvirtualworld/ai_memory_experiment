"""
向量存储层 (Vector Store) - Numpy 版

使用 Numpy + SQLite 实现 L4 混合记忆检索

功能：
- DashScope Embedding API (通义千问 text-embedding-v3)
- 向量存入 SQLite chat_messages.embedding 字段
- Numpy 余弦相似度计算
- 加权检索：Score = α·Recency + β·Similarity + γ·Importance
"""

import json
import requests
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from config import Config


@dataclass
class MemoryItem:
    """检索结果条目"""
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
        }


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
    向量存储管理器

    加权检索公式: Score = α·Recency + β·Similarity + γ·Importance
    权重: α=0.3, β=0.5, γ=0.2 (从 config.py 读取)
    """

    # 从 config.py 读取权重
    WEIGHTS = Config.MEMORY_OPERATIONS.get('hybrid_memory', {
        'alpha': 0.3,
        'beta': 0.5,
        'gamma': 0.2
    })

    def __init__(self, db_manager=None):
        """
        初始化

        Args:
            db_manager: DBManager 实例（用于数据库操作）
        """
        self.db = db_manager
        self.embedding_fn = DashScopeEmbedding()

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
