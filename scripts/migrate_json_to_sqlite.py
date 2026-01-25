"""
数据迁移脚本：JSON -> SQLite

将 data/users/*.json 中的数据迁移到 SQLite 数据库

使用方法：
    python scripts/migrate_json_to_sqlite.py

注意：
    - 迁移前会备份原 JSON 文件
    - 迁移是幂等的，重复运行会跳过已存在的用户
"""

import os
import sys
import json
import shutil
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_session, DBManager


def backup_json_files(data_dir: str, backup_dir: str):
    """备份 JSON 文件"""
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'users_backup_{timestamp}')

    users_dir = os.path.join(data_dir, 'users')
    if os.path.exists(users_dir):
        shutil.copytree(users_dir, backup_path)
        print(f"✓ 备份完成: {backup_path}")
        return backup_path
    return None


def load_json_users(data_dir: str) -> list:
    """加载所有 JSON 用户数据"""
    users = []
    users_dir = os.path.join(data_dir, 'users')

    if not os.path.exists(users_dir):
        print(f"✗ 用户目录不存在: {users_dir}")
        return users

    for filename in os.listdir(users_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(users_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    users.append(user_data)
                    print(f"  读取: {filename}")
            except Exception as e:
                print(f"  ✗ 读取失败 {filename}: {e}")

    return users


def migrate_users(db_manager: DBManager, users: list) -> dict:
    """迁移用户数据"""
    stats = {
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'messages': 0
    }

    for user_data in users:
        user_id = user_data.get('user_id', 'unknown')

        # 检查用户是否已存在
        if db_manager.get_user(user_id):
            print(f"  跳过 (已存在): {user_id}")
            stats['skipped'] += 1
            continue

        try:
            user = db_manager.import_from_json(user_data)
            if user:
                # 统计消息数
                msg_count = sum(
                    len(ts.get('conversation', []))
                    for ts in user_data.get('task_set', [])
                )
                stats['messages'] += msg_count
                stats['success'] += 1
                print(f"  ✓ 迁移成功: {user_id} ({msg_count} 条消息)")
            else:
                stats['failed'] += 1
                print(f"  ✗ 迁移失败: {user_id}")
        except Exception as e:
            stats['failed'] += 1
            print(f"  ✗ 迁移失败 {user_id}: {e}")

    return stats


def main():
    print("=" * 50)
    print("JSON -> SQLite 数据迁移工具")
    print("=" * 50)

    # 路径配置
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, 'data')
    db_path = os.path.join(data_dir, 'experiment.db')
    backup_dir = os.path.join(data_dir, 'backups')

    print(f"\n项目根目录: {project_root}")
    print(f"数据目录: {data_dir}")
    print(f"数据库路径: {db_path}")

    # 步骤 1: 备份
    print("\n[1/3] 备份 JSON 文件...")
    backup_path = backup_json_files(data_dir, backup_dir)

    # 步骤 2: 初始化数据库
    print("\n[2/3] 初始化 SQLite 数据库...")
    engine, SessionLocal = init_db(db_path)
    session = get_session(SessionLocal)
    db_manager = DBManager(session)
    print(f"✓ 数据库已创建: {db_path}")

    # 步骤 3: 迁移数据
    print("\n[3/3] 迁移用户数据...")
    users = load_json_users(data_dir)
    print(f"  共找到 {len(users)} 个用户文件")

    if users:
        stats = migrate_users(db_manager, users)

        print("\n" + "=" * 50)
        print("迁移完成统计:")
        print(f"  成功: {stats['success']} 用户")
        print(f"  跳过: {stats['skipped']} 用户 (已存在)")
        print(f"  失败: {stats['failed']} 用户")
        print(f"  消息: {stats['messages']} 条")
        print("=" * 50)
    else:
        print("  没有找到用户数据，跳过迁移")

    # 关闭会话
    session.close()

    print("\n✓ 迁移完成!")
    print(f"  数据库文件: {db_path}")
    if backup_path:
        print(f"  JSON 备份: {backup_path}")


if __name__ == '__main__':
    main()
