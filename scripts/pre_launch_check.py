"""
上云前快速检查脚本

检查所有关键功能是否正常
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_database():
    """检查数据库"""
    print("\n[1/6] 检查数据库...")
    try:
        from database import init_db, get_session, DBManager
        from database.models import User, UserProfile, ChatMessage
        from sqlalchemy import text

        engine, SessionLocal = init_db('data/experiment.db')
        session = get_session(SessionLocal)
        db = DBManager(session)

        # 检查表是否存在
        tables = ['users', 'user_tasks', 'chat_messages', 'user_profiles', 'experiment_logs']
        for table in tables:
            count = session.execute(
                text(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
            ).scalar()
            if count == 0:
                print(f"  ❌ 表 {table} 不存在")
                return False

        print("  ✅ 数据库检查通过（5个核心表）")
        session.close()
        return True
    except Exception as e:
        print(f"  ❌ 数据库错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_api_keys():
    """检查 API Key"""
    print("\n[2/6] 检查 API Key...")
    try:
        from config import Config

        qwen_key = Config.EXPERIMENT_CONFIG.get('qwen_api_key', '')

        if not qwen_key or qwen_key == 'your-api-key-here':
            print("  ❌ 通义千问 API Key 未配置")
            return False

        if qwen_key.startswith('sk-'):
            print(f"  ✅ API Key 已配置: {qwen_key[:10]}...")
        else:
            print("  ⚠️  API Key 格式可能不正确")

        return True
    except Exception as e:
        print(f"  ❌ 配置文件错误: {e}")
        return False


def check_services():
    """检查服务导入"""
    print("\n[3/6] 检查服务模块...")
    try:
        from services import MemoryEngine, TimerService, ConsolidationService
        from services.llm_service import QwenManager

        print("  ✅ 所有服务模块导入成功")
        return True
    except Exception as e:
        print(f"  ❌ 服务导入失败: {e}")
        return False


def check_embedding():
    """检查 Embedding API"""
    print("\n[4/6] 检查 Embedding API...")
    try:
        from database.vector_store import DashScopeEmbedding
        from config import Config

        api_key = Config.EXPERIMENT_CONFIG.get('qwen_api_key')
        emb = DashScopeEmbedding(api_key)

        # 简单测试（不实际调用 API，只检查初始化）
        if emb.api_key and emb.base_url:
            print("  ✅ Embedding 服务初始化成功")
            print("  ⚠️  未实际调用 API（避免消耗配额）")
            return True
        else:
            print("  ❌ Embedding 服务配置错误")
            return False
    except Exception as e:
        print(f"  ❌ Embedding 服务错误: {e}")
        return False


def check_admin_account():
    """检查管理员账号"""
    print("\n[5/6] 检查管理员账号...")
    try:
        from database import init_db, get_session, DBManager

        engine, SessionLocal = init_db('data/experiment.db')
        session = get_session(SessionLocal)
        db = DBManager(session)

        admin = db.get_user('admin')

        if admin:
            print(f"  ✅ 管理员账号存在: {admin.name}")
        else:
            print("  ⚠️  管理员账号不存在")
            print("     创建方法: 前端注册或运行 scripts/create_admin.py")

        session.close()
        return True
    except Exception as e:
        print(f"  ❌ 检查失败: {e}")
        return False


def check_frontend():
    """检查前端文件"""
    print("\n[6/6] 检查前端文件...")
    try:
        if os.path.exists('static/index.html'):
            size = os.path.getsize('static/index.html')
            print(f"  ✅ index.html 存在 ({size/1024:.1f} KB)")
            return True
        else:
            print("  ❌ index.html 不存在")
            return False
    except Exception as e:
        print(f"  ❌ 检查失败: {e}")
        return False


def main():
    print("=" * 60)
    print("上云前系统检查")
    print("=" * 60)

    results = []

    results.append(("数据库", check_database()))
    results.append(("API Key", check_api_keys()))
    results.append(("服务模块", check_services()))
    results.append(("Embedding", check_embedding()))
    results.append(("管理员账号", check_admin_account()))
    results.append(("前端文件", check_frontend()))

    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:12s} {status}")

    print("\n" + "-" * 60)
    print(f"总计: {passed}/{total} 项通过")

    if passed == total:
        print("\n🎉 所有检查通过！系统可以上线。")
        print("\n下一步:")
        print("  1. python app.py  # 启动服务")
        print("  2. 访问 http://localhost:8000")
        print("  3. 创建测试用户进行预实验")
    else:
        print("\n⚠️  部分检查未通过，请修复后再上线。")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
