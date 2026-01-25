"""
数据库模型测试脚本

验证 SQLAlchemy 模型和 DBManager 是否正常工作

使用方法：
    python scripts/test_db.py
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_models():
    """测试模型导入"""
    print("[1] 测试模型导入...")
    try:
        from database import User, UserTask, ChatMessage, ExperimentLog
        print("  ✓ 所有模型导入成功")
        return True
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}")
        return False


def test_db_init():
    """测试数据库初始化"""
    print("\n[2] 测试数据库初始化...")
    try:
        from database import init_db, get_session

        # 使用内存数据库测试
        engine, SessionLocal = init_db(':memory:')
        session = get_session(SessionLocal)
        print("  ✓ 数据库初始化成功 (内存模式)")
        session.close()
        return True, SessionLocal
    except Exception as e:
        print(f"  ✗ 初始化失败: {e}")
        return False, None


def test_crud(SessionLocal):
    """测试 CRUD 操作"""
    print("\n[3] 测试 CRUD 操作...")

    from database import DBManager, get_session

    session = get_session(SessionLocal)
    db = DBManager(session)

    try:
        # 创建用户
        user = db.create_user(
            user_id='test_user',
            username='test_user',
            name='测试用户',
            password='test123',
            age=25,
            gender='male',
            memory_group='hybrid_memory'
        )
        assert user is not None, "用户创建失败"
        print("  ✓ 创建用户成功")

        # 读取用户
        loaded_user = db.get_user('test_user')
        assert loaded_user is not None, "用户读取失败"
        assert loaded_user.name == '测试用户', "用户名称不匹配"
        print("  ✓ 读取用户成功")

        # 验证密码
        assert db.verify_password('test_user', 'test123'), "密码验证失败"
        assert not db.verify_password('test_user', 'wrong'), "错误密码不应验证通过"
        print("  ✓ 密码验证成功")

        # 创建任务
        task = db.get_or_create_user_task('test_user', 1)
        assert task is not None, "任务创建失败"
        print("  ✓ 创建任务成功")

        # 启动计时器
        timer_info = db.start_task_timer('test_user', 1)
        assert timer_info['total_duration'] == 900, "计时器总时长不正确"
        print("  ✓ 启动计时器成功")

        # 添加消息
        msg = db.add_message(
            user_id='test_user',
            task_id=1,
            content='你好，这是测试消息',
            is_user=True
        )
        assert msg is not None, "消息添加失败"
        print("  ✓ 添加消息成功")

        # 读取消息
        messages = db.get_task_messages('test_user', 1)
        assert len(messages) == 1, "消息读取数量不正确"
        assert messages[0].content == '你好，这是测试消息', "消息内容不匹配"
        print("  ✓ 读取消息成功")

        # 记录日志
        log = db.log_event('test_user', 'test_event', task_id=1, event_data={'test': True})
        assert log is not None, "日志记录失败"
        print("  ✓ 记录日志成功")

        # 获取统计
        stats = db.get_user_stats('test_user')
        assert stats['total_messages'] == 1, "消息统计不正确"
        print("  ✓ 获取统计成功")

        session.close()
        return True

    except AssertionError as e:
        print(f"  ✗ 断言失败: {e}")
        session.close()
        return False
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        session.close()
        return False


def main():
    print("=" * 50)
    print("数据库模型测试")
    print("=" * 50)

    # 测试 1: 模型导入
    if not test_models():
        print("\n✗ 测试失败: 模型导入错误")
        return

    # 测试 2: 数据库初始化
    success, SessionLocal = test_db_init()
    if not success:
        print("\n✗ 测试失败: 数据库初始化错误")
        return

    # 测试 3: CRUD 操作
    if not test_crud(SessionLocal):
        print("\n✗ 测试失败: CRUD 操作错误")
        return

    print("\n" + "=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)


if __name__ == '__main__':
    main()
