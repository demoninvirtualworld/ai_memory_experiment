"""
向量初始化脚本 (Numpy 版)

将 SQLite 中现有的对话记录生成向量并存入 chat_messages.embedding 字段

用法:
    python scripts/init_memory_vectors.py
    python scripts/init_memory_vectors.py --stats       # 仅查看统计
    python scripts/init_memory_vectors.py --test USER_ID "查询内容"  # 测试检索
    python scripts/init_memory_vectors.py --force       # 强制重新生成所有向量

功能:
    1. 读取 data/experiment.db 中的所有 ChatMessage
    2. 调用通义千问 text-embedding-v3 API 生成向量
    3. 计算每条消息的 importance_score
    4. 更新 SQLite chat_messages.embedding 和 importance_score 字段
"""

import os
import sys
import json
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, ChatMessage
from database.db_manager import DBManager
from database.vector_store import VectorStore, get_vector_store
from services.llm_service import estimate_importance_score


def init_memory_vectors(
    db_path: str = "data/experiment.db",
    force: bool = False,
    batch_size: int = 10
):
    """
    初始化消息向量

    Args:
        db_path: SQLite 数据库路径
        force: 是否强制重新生成所有向量（包括已有向量的消息）
        batch_size: 批处理大小（API 限制 25）
    """
    print("=" * 60)
    print("L4 向量初始化脚本 (Numpy + SQLite)")
    print("=" * 60)
    print(f"数据库: {db_path}")
    print(f"强制模式: {'是' if force else '否'}")
    print()

    # 1. 初始化数据库连接
    print("[1/5] 连接 SQLite 数据库...")
    engine, SessionLocal = init_db(db_path)
    db = DBManager(SessionLocal())

    # 2. 初始化 VectorStore
    print("[2/5] 初始化 VectorStore...")
    vector_store = VectorStore(db_manager=db)

    # 3. 获取需要处理的消息
    print("[3/5] 读取待处理消息...")

    if force:
        # 强制模式：处理所有消息
        messages = db.session.query(ChatMessage).all()
        print(f"       强制模式: 将处理全部 {len(messages)} 条消息")
    else:
        # 普通模式：只处理没有向量的消息
        messages = db.session.query(ChatMessage).filter(
            ChatMessage.embedding.is_(None)
        ).all()

        total_count = db.session.query(ChatMessage).count()
        print(f"       总消息数: {total_count}")
        print(f"       待处理数: {len(messages)} (无向量)")

    if not messages:
        print("\n[完成] 所有消息已有向量，无需处理")
        show_stats(db)
        return

    # 4. 批量处理
    print(f"[4/5] 开始向量化 (批大小: {batch_size})...")

    total_batches = (len(messages) + batch_size - 1) // batch_size
    success_count = 0
    fail_count = 0
    start_time = time.time()

    for batch_idx in range(0, len(messages), batch_size):
        batch = messages[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1

        print(f"       批次 {batch_num}/{total_batches}...", end=" ", flush=True)

        # 准备文本
        texts = [msg.content for msg in batch]

        # 批量生成向量
        embeddings = vector_store.generate_embeddings_batch(texts)

        # 更新数据库
        batch_success = 0
        batch_fail = 0

        for i, msg in enumerate(batch):
            embedding = embeddings[i] if i < len(embeddings) else None

            if embedding:
                # 计算重要性分数
                importance = estimate_importance_score(msg.content, msg.is_user)

                # 更新数据库
                msg.embedding = json.dumps(embedding)
                msg.importance_score = importance

                batch_success += 1
            else:
                batch_fail += 1

        # 提交本批次
        try:
            db.session.commit()
            success_count += batch_success
            fail_count += batch_fail
            print(f"成功: {batch_success}, 失败: {batch_fail}")
        except Exception as e:
            db.session.rollback()
            fail_count += len(batch)
            print(f"提交失败: {e}")

        # API 限速保护
        if batch_num < total_batches:
            time.sleep(0.5)

    elapsed = time.time() - start_time

    # 5. 完成统计
    print("[5/5] 处理完成")
    print("\n" + "=" * 60)
    print("初始化统计:")
    print(f"  - 处理消息数: {len(messages)}")
    print(f"  - 成功: {success_count}")
    print(f"  - 失败: {fail_count}")
    print(f"  - 耗时: {elapsed:.1f} 秒")
    print("=" * 60)

    # 显示最终状态
    show_stats(db)


def show_stats(db=None):
    """显示向量统计信息"""
    if db is None:
        engine, SessionLocal = init_db("data/experiment.db")
        db = DBManager(SessionLocal())

    vector_store = VectorStore(db_manager=db)
    stats = vector_store.get_stats()

    print("\n向量存储状态:")
    print(f"  总消息数: {stats.get('total_messages', 0)}")
    print(f"  已向量化: {stats.get('with_embedding', 0)}")
    print(f"  覆盖率:   {stats.get('coverage', '0%')}")

    # 按用户统计
    from database import User
    users = db.session.query(User).all()
    if users:
        print("\n按用户统计:")
        for user in users:
            user_stats = vector_store.get_stats(user.user_id)
            print(f"  - {user.user_id}: {user_stats.get('with_embedding', 0)}/{user_stats.get('total_messages', 0)} ({user_stats.get('coverage', '0%')})")


def test_search(user_id: str, query: str):
    """测试向量检索"""
    print(f"\n测试检索:")
    print(f"  用户: {user_id}")
    print(f"  查询: {query}")
    print()

    engine, SessionLocal = init_db("data/experiment.db")
    db = DBManager(SessionLocal())
    vector_store = VectorStore(db_manager=db)

    results = vector_store.search_weighted(
        user_id=user_id,
        query=query,
        top_k=5
    )

    if results:
        print(f"找到 {len(results)} 条相关记忆:\n")
        for i, mem in enumerate(results, 1):
            role = "用户" if mem.is_user else "AI"
            content_preview = mem.content[:80] + "..." if len(mem.content) > 80 else mem.content

            print(f"[{i}] Task {mem.task_id} ({role})")
            print(f"    内容: {content_preview}")
            print(f"    相似度: {mem.similarity_score:.3f} | 新鲜度: {mem.recency_score:.3f} | 重要性: {mem.importance_score:.3f}")
            print(f"    最终分: {mem.final_score:.3f}")
            print()
    else:
        print("  未找到相关记忆")


def test_api_single():
    """测试单条消息的 Embedding API"""
    print("\n测试 Embedding API 连接...")

    engine, SessionLocal = init_db("data/experiment.db")
    db = DBManager(SessionLocal())
    vector_store = VectorStore(db_manager=db)

    # 调用测试方法
    success = vector_store.embedding_fn.test_single("你好，这是一条测试消息")

    if success:
        print("\nAPI 配置正确，可以运行完整初始化")
    else:
        print("\n请检查:")
        print("  1. API Key 是否正确 (config.py 中的 qwen_api_key)")
        print("  2. 网络连接是否正常")
        print("  3. API 余额是否充足")


def verify_embeddings():
    """验证向量数据完整性"""
    print("\n验证向量数据完整性...")

    engine, SessionLocal = init_db("data/experiment.db")
    db = DBManager(SessionLocal())

    # 检查有向量的消息
    messages_with_embedding = db.session.query(ChatMessage).filter(
        ChatMessage.embedding.isnot(None)
    ).limit(5).all()

    if messages_with_embedding:
        print(f"\n抽样检查 {len(messages_with_embedding)} 条有向量的消息:")
        for msg in messages_with_embedding:
            try:
                embedding = json.loads(msg.embedding)
                dim = len(embedding)
                preview = str(embedding[:3])[:30] + "..."
                print(f"  - {msg.message_id}: 维度={dim}, 重要性={msg.importance_score:.2f}, 向量={preview}")
            except Exception as e:
                print(f"  - {msg.message_id}: 解析错误 - {e}")
    else:
        print("  没有找到有向量的消息")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="L4 向量初始化工具 (Numpy 版)")
    parser.add_argument("--force", action="store_true", help="强制重新生成所有向量")
    parser.add_argument("--stats", action="store_true", help="仅显示统计信息")
    parser.add_argument("--verify", action="store_true", help="验证向量数据完整性")
    parser.add_argument("--api-test", action="store_true", help="测试单条消息的 Embedding API")
    parser.add_argument("--test", nargs=2, metavar=("USER_ID", "QUERY"), help="测试向量检索")
    parser.add_argument("--db", default="data/experiment.db", help="数据库路径")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    elif args.verify:
        verify_embeddings()
    elif args.api_test:
        test_api_single()
    elif args.test:
        test_search(args.test[0], args.test[1])
    else:
        init_memory_vectors(db_path=args.db, force=args.force)
