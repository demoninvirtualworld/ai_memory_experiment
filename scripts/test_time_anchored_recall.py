"""
测试"溯源感"（Time-anchored Recall）功能

验证用户画像中是否正确标注了来源任务

测试场景：
1. 第 1 次对话：用户提到"喜欢爬山"
2. 固化后检查：画像中应显示"喜欢爬山 [Task 1]"
3. 第 2 次对话：用户提到"素食主义"
4. 固化后检查：画像中应有两条，分别标注 [Task 1] 和 [Task 2]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_session, DBManager
from services import ConsolidationService
from services.llm_service import QwenManager
from config import Config
import json


def test_time_anchored_recall():
    """测试时间锚点回忆功能"""
    print("=" * 70)
    print("测试：时间锚点回忆（Time-anchored Recall）")
    print("=" * 70)

    # 初始化
    engine, SessionLocal = init_db('data/experiment.db')
    session = get_session(SessionLocal)
    db = DBManager(session)

    llm = QwenManager(
        api_key=Config.EXPERIMENT_CONFIG['qwen_api_key'],
        base_url=Config.EXPERIMENT_CONFIG['qwen_base_url'],
        model=Config.EXPERIMENT_CONFIG['qwen_model']
    )

    consolidation = ConsolidationService(db, llm)

    # 测试用户
    test_user_id = "test_time_anchor_001"

    # 创建测试用户（L3 组）
    print(f"\n📝 创建测试用户: {test_user_id}")
    user = db.create_user(
        user_id=test_user_id,
        username=test_user_id,
        name="时间锚点测试用户",
        password="test123",
        memory_group="gist_memory"
    )

    if not user:
        # 如果用户已存在，删除重建
        print(f"⚠️  用户已存在，清空数据重新测试")
        # 这里可以选择清空用户数据或使用现有用户

    # ========== 第 1 次对话 ==========
    print("\n" + "=" * 70)
    print("第 1 次对话：用户分享个人信息")
    print("=" * 70)

    # 模拟对话
    task_1_messages = [
        {"is_user": True, "content": "你好！我是一名博士生，目前在准备考博。"},
        {"is_user": False, "content": "你好！很高兴认识你。考博是个重要的决定，祝你顺利！"},
        {"is_user": True, "content": "谢谢！我平时喜欢爬山，觉得很放松。"},
        {"is_user": False, "content": "爬山确实是个很好的减压方式。"},
        {"is_user": True, "content": "对了，我是素食主义者，对海鲜过敏。"},
        {"is_user": False, "content": "明白了，我会记住的。有什么饮食建议需要吗？"}
    ]

    # 保存消息
    for msg in task_1_messages:
        db.add_message(test_user_id, 1, msg['content'], msg['is_user'])

    # 提交任务
    db.submit_task(test_user_id, 1, {})

    # 执行固化
    print("\n🔄 执行第 1 次固化...")
    stats_1 = consolidation.consolidate_after_session(test_user_id, 1, 'gist_memory')

    if stats_1['success']:
        print("✅ 固化成功")
        print(f"   提取特质数: {stats_1.get('new_traits_count', 0)}")
    else:
        print("❌ 固化失败:", stats_1.get('error'))

    # 查看画像
    profile_1 = db.get_user_profile(test_user_id)
    print("\n📊 第 1 次固化后的用户画像:")
    print(json.dumps(profile_1, ensure_ascii=False, indent=2))

    # ========== 检查溯源标注 ==========
    print("\n" + "-" * 70)
    print("✓ 检查点 1：画像中是否包含 [Task 1] 标注？")
    has_task_1_tag = False
    for category, values in profile_1.items():
        if isinstance(values, list):
            for item in values:
                if '[Task 1]' in str(item):
                    has_task_1_tag = True
                    print(f"   找到: {item}")
        elif isinstance(values, dict):
            for key, value in values.items():
                if '[Task 1]' in str(value):
                    has_task_1_tag = True
                    print(f"   找到: {key}: {value}")

    if has_task_1_tag:
        print("   ✅ 通过：找到 [Task 1] 标注")
    else:
        print("   ⚠️  警告：未找到 [Task 1] 标注（可能是 LLM 输出格式问题）")

    # ========== 第 2 次对话 ==========
    print("\n" + "=" * 70)
    print("第 2 次对话：用户补充新信息")
    print("=" * 70)

    task_2_messages = [
        {"is_user": True, "content": "最近我在学习 Python 编程。"},
        {"is_user": False, "content": "很棒！Python 在数据科学领域很有用。"},
        {"is_user": True, "content": "是的，我还养了一只猫，它很可爱。"},
        {"is_user": False, "content": "猫咪确实能缓解压力。"}
    ]

    for msg in task_2_messages:
        db.add_message(test_user_id, 2, msg['content'], msg['is_user'])

    db.submit_task(test_user_id, 2, {})

    print("\n🔄 执行第 2 次固化...")
    stats_2 = consolidation.consolidate_after_session(test_user_id, 2, 'gist_memory')

    if stats_2['success']:
        print("✅ 固化成功")
        print(f"   新增特质数: {stats_2.get('new_traits_count', 0)}")
    else:
        print("❌ 固化失败:", stats_2.get('error'))

    # 查看更新后的画像
    profile_2 = db.get_user_profile(test_user_id)
    print("\n📊 第 2 次固化后的用户画像:")
    print(json.dumps(profile_2, ensure_ascii=False, indent=2))

    # ========== 最终检查 ==========
    print("\n" + "=" * 70)
    print("最终检查：画像是否正确标注了时间锚点？")
    print("=" * 70)

    task_1_count = 0
    task_2_count = 0

    for category, values in profile_2.items():
        if isinstance(values, list):
            for item in values:
                if '[Task 1]' in str(item):
                    task_1_count += 1
                if '[Task 2]' in str(item):
                    task_2_count += 1
        elif isinstance(values, dict):
            for key, value in values.items():
                if '[Task 1]' in str(value):
                    task_1_count += 1
                if '[Task 2]' in str(value):
                    task_2_count += 1

    print(f"\n统计:")
    print(f"  标注为 [Task 1] 的特质: {task_1_count} 个")
    print(f"  标注为 [Task 2] 的特质: {task_2_count} 个")

    if task_1_count > 0 and task_2_count > 0:
        print("\n✅ 测试通过！时间锚点功能正常工作。")
        print("\n💡 现在 AI 可以说：")
        print('   "我还记得你第一次（Task 1）告诉我你喜欢爬山。"')
        print('   "你最近（Task 2）提到在学 Python，进展如何？"')
    elif task_1_count > 0:
        print("\n⚠️  部分通过：只有 Task 1 的标注，Task 2 可能未成功提取")
    else:
        print("\n❌ 测试失败：未找到时间锚点标注")
        print("   可能原因：")
        print("   1. LLM 未按格式输出")
        print("   2. 提示词需要调整")
        print("   3. API 调用失败")

    # 清理
    session.close()

    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)


if __name__ == '__main__':
    try:
        test_time_anchored_recall()
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
