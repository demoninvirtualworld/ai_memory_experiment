"""
测试情感显著性计算方法

对比三种方法的效果：
1. 规则方法（原方法）
2. LLM方法
3. 混合方法（推荐）
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.consolidation_service import ConsolidationService
from services.llm_service import QwenManager
from database import DBManager, init_db, get_session
from config import Config


def test_emotional_salience():
    """测试不同方法的情感显著性计算"""

    print("=" * 80)
    print("情感显著性计算方法对比测试")
    print("=" * 80)

    # 初始化数据库
    engine, SessionLocal = init_db('data/experiment.db')
    session = get_session(SessionLocal)
    db = DBManager(session)

    # 初始化LLM（从config读取API key）
    api_key = Config.EXPERIMENT_CONFIG.get('qwen_api_key')
    llm = QwenManager(api_key=api_key)

    consolidation = ConsolidationService(db, llm)

    # 测试用例
    test_cases = [
        # (消息内容, 预期类型)
        ("今天天气不错", "无情感"),
        ("我去图书馆了", "无情感"),
        ("有点累", "轻微情感"),
        ("我太开心了！", "高情感强度"),
        ("呵呵，随便吧", "隐含情感（冷漠/失望）"),
        ("其实我一直很焦虑", "高自我披露+情感"),
        ("我从没告诉过别人，我很害怕失败", "极高自我披露"),
        ("家人是我人生最重要的", "核心价值观"),
        ("说实话，我对未来很迷茫，压力太大了", "综合高分"),
        ("我今天早上8点吃了面包", "客观事实"),
    ]

    print("\n" + "=" * 80)
    print("开始测试...")
    print("=" * 80 + "\n")

    results = []

    for i, (content, expected_type) in enumerate(test_cases, 1):
        print(f"[测试 {i}/{len(test_cases)}] {content}")
        print(f"预期类型: {expected_type}")
        print("-" * 80)

        # 方法1: 规则方法
        rule_score = consolidation._calculate_emotional_salience(content, is_user=True)
        print(f"[OK] 规则方法: {rule_score:.3f}")

        # 方法2: LLM方法
        llm_score = consolidation._calculate_emotional_salience_llm(content, is_user=True)
        print(f"[OK] LLM方法:  {llm_score:.3f}")

        # 方法3: 混合方法
        hybrid_score = consolidation._calculate_emotional_salience_hybrid(content, is_user=True)
        print(f"[OK] 混合方法: {hybrid_score:.3f}")

        results.append({
            'content': content,
            'type': expected_type,
            'rule': rule_score,
            'llm': llm_score,
            'hybrid': hybrid_score
        })

        print("\n")

    # 统计分析
    print("=" * 80)
    print("统计分析")
    print("=" * 80)

    # 计算差异
    rule_llm_diff = sum(abs(r['rule'] - r['llm']) for r in results) / len(results)
    rule_hybrid_diff = sum(abs(r['rule'] - r['hybrid']) for r in results) / len(results)

    print(f"\n平均绝对差异：")
    print(f"  规则 vs LLM:  {rule_llm_diff:.3f}")
    print(f"  规则 vs 混合: {rule_hybrid_diff:.3f}")

    # 统计LLM调用次数
    llm_calls = sum(1 for r in results if r['hybrid'] != r['rule'])
    llm_rate = llm_calls / len(results) * 100

    print(f"\n混合方法LLM调用率：")
    print(f"  调用次数: {llm_calls}/{len(results)}")
    print(f"  调用率:   {llm_rate:.1f}%")
    print(f"  节省率:   {100-llm_rate:.1f}%")

    # 详细对比表
    print("\n" + "=" * 80)
    print("详细对比表")
    print("=" * 80)
    print(f"{'消息':<30} {'预期':<15} {'规则':<8} {'LLM':<8} {'混合':<8}")
    print("-" * 80)

    for r in results:
        content_short = r['content'][:28] + '..' if len(r['content']) > 28 else r['content']
        print(f"{content_short:<30} {r['type']:<15} "
              f"{r['rule']:<8.3f} {r['llm']:<8.3f} {r['hybrid']:<8.3f}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

    # 给出建议
    print("\n📊 建议：")
    if llm_rate < 30:
        print(f"  ✅ 混合方法表现良好！LLM调用率仅{llm_rate:.1f}%，成本可控。")
    elif llm_rate < 50:
        print(f"  ⚠️  LLM调用率{llm_rate:.1f}%，可考虑提高阈值（当前{Config.EXPERIMENT_CONFIG['emotional_salience']['llm_threshold']}）")
    else:
        print(f"  ⚠️  LLM调用率过高（{llm_rate:.1f}%），建议提高阈值或检查规则方法")

    if rule_llm_diff > 0.3:
        print(f"  ✅ LLM方法与规则方法差异明显（{rule_llm_diff:.3f}），说明LLM捕捉到了更多隐含情感")
    else:
        print(f"  ℹ️  差异较小（{rule_llm_diff:.3f}），可能测试用例情感较弱")


def test_single_message():
    """测试单条消息（交互式）"""

    print("\n" + "=" * 80)
    print("单条消息测试（交互式）")
    print("=" * 80)

    # 初始化数据库
    engine, SessionLocal = init_db('data/experiment.db')
    session = get_session(SessionLocal)
    db = DBManager(session)

    # 初始化LLM（从config读取API key）
    api_key = Config.EXPERIMENT_CONFIG.get('qwen_api_key')
    llm = QwenManager(api_key=api_key)

    consolidation = ConsolidationService(db, llm)

    while True:
        print("\n请输入要测试的消息（输入'quit'退出）：")
        content = input("> ")

        if content.lower() == 'quit':
            break

        if not content.strip():
            print("消息不能为空！")
            continue

        print("\n" + "-" * 80)
        print(f"消息: {content}")
        print("-" * 80)

        # 规则方法
        rule_score = consolidation._calculate_emotional_salience(content, is_user=True)
        print(f"规则方法: {rule_score:.3f}")

        # LLM方法
        llm_score = consolidation._calculate_emotional_salience_llm(content, is_user=True)

        # 混合方法
        hybrid_score = consolidation._calculate_emotional_salience_hybrid(content, is_user=True)
        print(f"混合方法: {hybrid_score:.3f}")

        print("-" * 80)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='测试情感显著性计算方法')
    parser.add_argument('--mode', choices=['batch', 'interactive'], default='batch',
                        help='测试模式: batch(批量测试) 或 interactive(交互式)')

    args = parser.parse_args()

    if args.mode == 'batch':
        test_emotional_salience()
    else:
        test_single_message()
