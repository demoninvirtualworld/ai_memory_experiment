"""
手动记忆固化脚本

用于在自动固化失败时手动修复

使用场景：
1. API 抖动导致固化失败
2. LLM 输出格式错误
3. 数据库临时不可用

用法：
    python scripts/manual_consolidation.py --user USER_ID --task TASK_ID
    python scripts/manual_consolidation.py --user test_001 --task 1
    python scripts/manual_consolidation.py --user test_001 --all  # 重跑所有失败的任务
    python scripts/manual_consolidation.py --check-failed  # 查看所有失败记录
"""

import sys
import os
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_session, DBManager
from services import ConsolidationService
from services.llm_service import QwenManager, DeepSeekManager
from config import Config


def init_services():
    """初始化服务"""
    # 数据库
    engine, SessionLocal = init_db('data/experiment.db')
    session = get_session(SessionLocal)
    db = DBManager(session)

    # LLM
    experiment_config = Config.EXPERIMENT_CONFIG
    if experiment_config['model_provider'] == 'qwen':
        llm = QwenManager(
            api_key=experiment_config['qwen_api_key'],
            base_url=experiment_config['qwen_base_url'],
            model=experiment_config['qwen_model']
        )
    else:
        llm = DeepSeekManager(
            api_key=experiment_config['deepseek_api_key'],
            base_url=experiment_config['deepseek_base_url']
        )

    # 固化服务
    consolidation = ConsolidationService(db, llm)

    return db, consolidation, session


def check_failed_consolidations(db: DBManager):
    """查看所有固化失败的记录"""
    print("\n" + "=" * 60)
    print("固化失败记录查询")
    print("=" * 60)

    # 查询失败日志
    from database.models import ExperimentLog

    failed_logs = db.session.query(ExperimentLog).filter(
        ExperimentLog.event_type == 'consolidation_failed'
    ).order_by(ExperimentLog.timestamp.desc()).all()

    if not failed_logs:
        print("\n✅ 没有失败记录！所有固化都成功了。")
        return []

    print(f"\n共找到 {len(failed_logs)} 条失败记录：\n")

    failed_tasks = []
    for i, log in enumerate(failed_logs, 1):
        event_data = log.event_data or {}
        print(f"{i}. User: {log.user_id}, Task: {log.task_id}")
        print(f"   时间: {log.timestamp}")
        print(f"   记忆组: {event_data.get('memory_group', 'unknown')}")
        print(f"   错误类型: {event_data.get('error_category', 'unknown')}")
        print(f"   错误详情: {event_data.get('error', 'N/A')[:100]}...")
        print()

        failed_tasks.append({
            'user_id': log.user_id,
            'task_id': log.task_id,
            'memory_group': event_data.get('memory_group'),
            'timestamp': log.timestamp
        })

    return failed_tasks


def manual_consolidate(db: DBManager, consolidation: ConsolidationService, user_id: str, task_id: int):
    """手动执行固化"""
    print("\n" + "=" * 60)
    print(f"手动固化: User={user_id}, Task={task_id}")
    print("=" * 60)

    # 获取用户信息
    user = db.get_user(user_id)
    if not user:
        print(f"❌ 错误：用户 {user_id} 不存在")
        return False

    memory_group = user.memory_group
    print(f"\n用户记忆组: {memory_group}")

    # 检查任务是否存在
    task = db.get_or_create_user_task(user_id, task_id)
    if not task.submitted:
        print(f"⚠️  警告：任务 {task_id} 尚未提交，是否仍要固化？")
        confirm = input("继续吗？(y/n): ")
        if confirm.lower() != 'y':
            print("已取消")
            return False

    # 执行固化
    print(f"\n🔄 开始固化...")
    stats = consolidation.consolidate_after_session(user_id, task_id, memory_group)

    # 显示结果
    print("\n" + "-" * 60)
    if stats['success']:
        print("✅ 固化成功！")
        print(f"\n固化统计:")
        for key, value in stats.items():
            if key not in ['success', 'user_id', 'task_id', 'memory_group']:
                print(f"  {key}: {value}")

        # 如果是 L3，显示画像
        if memory_group == 'gist_memory':
            print("\n📊 用户画像:")
            profile = db.get_user_profile(user_id)
            import json
            print(json.dumps(profile, ensure_ascii=False, indent=2))

        return True
    else:
        print("❌ 固化失败！")
        print(f"\n错误信息:")
        print(f"  错误类型: {stats.get('error_type', 'unknown')}")
        print(f"  错误分类: {stats.get('error_category', 'unknown')}")
        print(f"  详细错误: {stats.get('error', 'N/A')}")
        return False


def consolidate_all_failed(db: DBManager, consolidation: ConsolidationService):
    """重跑所有失败的固化"""
    failed_tasks = check_failed_consolidations(db)

    if not failed_tasks:
        return

    print("\n" + "=" * 60)
    confirm = input(f"\n是否重跑所有 {len(failed_tasks)} 个失败的任务？(y/n): ")
    if confirm.lower() != 'y':
        print("已取消")
        return

    success_count = 0
    fail_count = 0

    for task in failed_tasks:
        print(f"\n处理: User={task['user_id']}, Task={task['task_id']}")
        if manual_consolidate(db, consolidation, task['user_id'], task['task_id']):
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"批量重跑完成:")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='手动记忆固化工具')
    parser.add_argument('--user', type=str, help='用户ID')
    parser.add_argument('--task', type=int, help='任务ID')
    parser.add_argument('--all', action='store_true', help='重跑指定用户的所有已提交任务')
    parser.add_argument('--check-failed', action='store_true', help='查看所有失败记录')

    args = parser.parse_args()

    # 初始化
    db, consolidation, session = init_services()

    try:
        if args.check_failed:
            # 查看失败记录
            check_failed_consolidations(db)

        elif args.user and args.task:
            # 单个任务固化
            manual_consolidate(db, consolidation, args.user, args.task)

        elif args.user and args.all:
            # 用户所有任务
            user = db.get_user(args.user)
            if not user:
                print(f"❌ 用户 {args.user} 不存在")
                return

            tasks = db.get_user_tasks(args.user)
            submitted_tasks = [t for t in tasks if t.submitted]

            if not submitted_tasks:
                print(f"用户 {args.user} 没有已提交的任务")
                return

            print(f"\n用户 {args.user} 有 {len(submitted_tasks)} 个已提交任务")
            confirm = input("是否全部重跑？(y/n): ")
            if confirm.lower() != 'y':
                print("已取消")
                return

            for task in submitted_tasks:
                manual_consolidate(db, consolidation, args.user, task.task_id)

        else:
            parser.print_help()
            print("\n示例用法:")
            print("  python scripts/manual_consolidation.py --check-failed")
            print("  python scripts/manual_consolidation.py --user test_001 --task 1")
            print("  python scripts/manual_consolidation.py --user test_001 --all")

    finally:
        session.close()


if __name__ == '__main__':
    main()
