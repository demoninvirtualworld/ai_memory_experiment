"""
端到端测试：LLM情感显著性在L4记忆系统中的实际效果

测试流程：
1. 模拟用户在Task 1中的对话（含高情感消息）
2. 触发固化（计算情感显著性）
3. 在Task 2中检索（验证情感加成效果）
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_session, DBManager
from database.vector_store import get_vector_store
from services.consolidation_service import ConsolidationService
from services.llm_service import QwenManager
from services.memory_engine import MemoryEngine
from config import Config
import time


def test_end_to_end():
    """端到端测试"""

    print("=" * 80)
    print("端到端测试：LLM情感显著性在L4系统中的实际效果")
    print("=" * 80)

    # 初始化
    print("\n[步骤1] 初始化数据库和服务...")
    engine, SessionLocal = init_db('data/experiment.db')
    session = get_session(SessionLocal)
    db = DBManager(session)

    api_key = Config.EXPERIMENT_CONFIG.get('qwen_api_key')
    llm = QwenManager(api_key=api_key)

    consolidation = ConsolidationService(db, llm)
    memory_engine = MemoryEngine(db, llm)

    # 创建测试用户
    test_user_id = 'test_emotional_user_001'

    # 清理旧数据
    print(f"[步骤2] 清理用户 {test_user_id} 的旧数据...")
    try:
        from database.models import User, ChatMessage, UserTask, UserProfile
        session.query(ChatMessage).filter(ChatMessage.user_id == test_user_id).delete()
        session.query(UserTask).filter(UserTask.user_id == test_user_id).delete()
        session.query(UserProfile).filter(UserProfile.user_id == test_user_id).delete()
        session.query(User).filter(User.user_id == test_user_id).delete()
        session.commit()
        print("  清理完成")
    except Exception as e:
        print(f"  清理失败（可能用户不存在）: {e}")
        session.rollback()

    # 创建用户
    print(f"[步骤3] 创建测试用户...")
    user = db.create_user(
        user_id=test_user_id,
        username='test_emotional',
        name='情感测试用户',
        password='test123',
        user_type='normal',
        memory_group='hybrid_memory'  # 使用L4混合记忆
    )
    print(f"  用户创建成功: {user.user_id}, 记忆组: {user.memory_group}")

    # ============ Task 1: 模拟对话（含情感消息） ============

    print("\n" + "=" * 80)
    print("[Task 1] 模拟用户对话（含高情感消息）")
    print("=" * 80)

    task_1_id = 1

    # 创建Task 1
    task1 = db.get_or_create_user_task(test_user_id, task_1_id)

    # 模拟对话
    conversations = [
        # 轮次1: 基本信息
        ("我是一名博士生，在研究人工智能", False),
        ("很高兴认识你！你研究AI的哪个方向呢？", True),

        # 轮次2: 情感披露（高情感强度）
        ("说实话，我对未来很迷茫，压力太大了", False),  # ← 高情感
        ("我理解你的感受。读博确实压力很大。能具体说说是什么让你感到压力吗？", True),

        # 轮次3: 深度自我披露
        ("我从没告诉过别人，我很害怕自己做不出成果", False),  # ← 极高自我披露
        ("感谢你愿意和我分享这些。害怕失败是很正常的情绪。", True),

        # 轮次4: 核心价值观
        ("家人对我来说是最重要的，但我现在几乎没时间陪他们", False),  # ← 核心价值观
        ("家人的支持很重要。也许可以尝试定期和他们视频通话？", True),

        # 轮次5: 普通对话
        ("今天去图书馆看了会儿文献", False),
        ("有什么收获吗？", True),
    ]

    print("\n对话记录：")
    for i, (content, is_ai) in enumerate(conversations, 1):
        role = "AI" if is_ai else "用户"
        db.add_message(test_user_id, task_1_id, content, is_user=(not is_ai))
        print(f"  [{i}] {role}: {content[:40]}{'...' if len(content) > 40 else ''}")

    print(f"\n  共 {len(conversations)} 条消息已保存")

    # ============ 固化阶段：计算情感显著性 ============

    print("\n" + "=" * 80)
    print("[固化阶段] 计算情感显著性并生成向量")
    print("=" * 80)

    print("\n开始固化...")
    result = consolidation.consolidate_after_session(
        user_id=test_user_id,
        task_id=task_1_id,
        memory_group='hybrid_memory'
    )

    print(f"\n固化结果:")
    print(f"  状态: {'成功' if result.get('success') else '失败'}")
    print(f"  动作: {result.get('action')}")
    if result.get('success'):
        print(f"  处理消息数: {result.get('total_messages', 0)}")
        print(f"  成功: {result.get('success', 0)}")
        print(f"  失败: {result.get('failed', 0)}")

    # 查看情感显著性分数
    print("\n" + "=" * 80)
    print("[验证] 情感显著性分数")
    print("=" * 80)

    messages = db.get_task_messages(test_user_id, task_1_id)

    print(f"\n消息情感分数详情:")
    print(f"{'消息内容':<40} {'角色':<6} {'情感分数':<10} {'重要性':<10}")
    print("-" * 80)

    high_emotional_messages = []

    for msg in messages:
        if msg.is_user:  # 只看用户消息
            content_short = msg.content[:38] + '..' if len(msg.content) > 38 else msg.content
            emotional = msg.emotional_salience or 0.0
            importance = msg.importance_score or 0.0

            print(f"{content_short:<40} {'用户':<6} {emotional:<10.3f} {importance:<10.3f}")

            # 记录高情感消息
            if emotional >= 0.5:
                high_emotional_messages.append({
                    'content': msg.content,
                    'emotional_salience': emotional,
                    'importance': importance,
                    'message_id': msg.message_id
                })

    print(f"\n高情感消息统计（分数 >= 0.5）:")
    print(f"  共 {len(high_emotional_messages)} 条")
    for i, msg in enumerate(high_emotional_messages, 1):
        print(f"  [{i}] {msg['content'][:50]}... (分数: {msg['emotional_salience']:.3f})")

    # ============ Task 2: 情感相关检索 ============

    print("\n" + "=" * 80)
    print("[Task 2] 情感相关检索测试")
    print("=" * 80)

    task_2_id = 2
    task2 = db.get_or_create_user_task(test_user_id, task_2_id)

    # 测试查询（情感相关）
    test_queries = [
        "我感觉压力好大",  # 应该召回Task 1中的压力相关消息
        "最近很担心家人",  # 应该召回Task 1中的家人相关消息
        "害怕失败怎么办",  # 应该召回Task 1中的害怕失败消息
    ]

    vector_store = get_vector_store(db)

    for query in test_queries:
        print(f"\n查询: \"{query}\"")
        print("-" * 80)

        # 使用动态遗忘曲线检索（含情感加成）
        results = vector_store.search_with_forgetting_curve(
            user_id=test_user_id,
            query=query,
            exclude_task_id=task_2_id,
            top_k=3,
            update_on_recall=False  # 测试时不更新
        )

        if results:
            print(f"  检索到 {len(results)} 条记忆:")
            for i, mem in enumerate(results, 1):
                print(f"\n  [{i}] 消息: {mem.content[:60]}{'...' if len(mem.content) > 60 else ''}")
                print(f"      相似度: {mem.similarity_score:.3f}")
                print(f"      召回概率: {mem.recall_probability:.3f}")
                print(f"      情感显著性: {mem.emotional_salience:.3f}")
                print(f"      情感加成: {mem.emotional_salience * 0.1:.3f}")

                # 计算基础概率（无情感加成）
                base_prob = mem.recall_probability - mem.emotional_salience * 0.1
                print(f"      基础概率: {base_prob:.3f}")
                print(f"      提升幅度: +{(mem.emotional_salience * 0.1 / base_prob * 100) if base_prob > 0 else 0:.1f}%")
        else:
            print("  未检索到相关记忆")

    # ============ 对比分析 ============

    print("\n" + "=" * 80)
    print("[对比分析] 情感加成的实际效果")
    print("=" * 80)

    # 统计高情感消息的召回率
    print("\n高情感消息召回统计:")

    all_recalled_ids = set()
    for query in test_queries:
        results = vector_store.search_with_forgetting_curve(
            user_id=test_user_id,
            query=query,
            exclude_task_id=task_2_id,
            top_k=5,
            update_on_recall=False
        )
        for mem in results:
            all_recalled_ids.add(mem.message_id)

    high_emotional_ids = {msg['message_id'] for msg in high_emotional_messages}
    recalled_high_emotional = high_emotional_ids & all_recalled_ids

    recall_rate = len(recalled_high_emotional) / len(high_emotional_ids) * 100 if high_emotional_ids else 0

    print(f"  高情感消息总数: {len(high_emotional_ids)}")
    print(f"  被召回数: {len(recalled_high_emotional)}")
    print(f"  召回率: {recall_rate:.1f}%")

    # 计算平均情感加成
    total_boost = 0
    boost_count = 0

    for query in test_queries:
        results = vector_store.search_with_forgetting_curve(
            user_id=test_user_id,
            query=query,
            exclude_task_id=task_2_id,
            top_k=5,
            update_on_recall=False
        )
        for mem in results:
            if mem.emotional_salience > 0:
                boost = mem.emotional_salience * 0.1
                base = mem.recall_probability - boost
                if base > 0:
                    relative_boost = boost / base * 100
                    total_boost += relative_boost
                    boost_count += 1

    avg_boost = total_boost / boost_count if boost_count > 0 else 0

    print(f"\n情感加成效果:")
    print(f"  平均相对提升: {avg_boost:.1f}%")
    print(f"  有效加成次数: {boost_count}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

    # 清理
    session.close()


if __name__ == '__main__':
    test_end_to_end()
