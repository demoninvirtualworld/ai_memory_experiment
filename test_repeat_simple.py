#!/usr/bin/env python3
"""
简单测试脚本：验证AI不会评论重复提问
假设应用已经在运行 (http://localhost:8000)
"""

import requests
import json
import time
import sys

def test_repeat_question():
    """测试重复提问场景"""
    print("\n=== 测试重复提问（使用运行中的应用）===")

    # 1. 注册测试用户
    register_data = {
        'username': f'test_repeat_user_{int(time.time())}',
        'password': 'test123',
        'name': '测试用户',
        'age': 25,
        'gender': 'male',
        'memory_group': 'working_memory',
        'ethics_consent_accepted': True
    }

    try:
        response = requests.post(
            'http://localhost:8000/api/auth/register',
            json=register_data,
            timeout=5
        )

        if response.status_code != 200:
            print(f"注册失败: {response.status_code} - {response.text}")
            return False

        result = response.json()
        if not result.get('success'):
            print(f"注册失败: {result.get('message')}")
            return False

        session_token = result['data']['session_token']
        user_id = result['data']['user']['id']
        print(f"注册成功，用户: {user_id}, token: {session_token[:20]}...")

        # 2. 获取当前任务
        headers = {'Authorization': f'Bearer {session_token}'}
        response = requests.get(
            'http://localhost:8000/api/users/me/tasks/current',
            headers=headers,
            timeout=5
        )

        if response.status_code != 200:
            print(f"获取任务失败: {response.status_code}")
            return False

        task_result = response.json()
        if not task_result.get('success'):
            print(f"获取任务失败: {task_result.get('message')}")
            return False

        task = task_result['data']
        if not task:
            print("没有可用任务")
            return False

        task_id = task['id']
        print(f"当前任务: {task_id} - {task['title']}")

        # 3. 启动任务计时器
        response = requests.post(
            f'http://localhost:8000/api/users/me/tasks/{task_id}/start',
            headers=headers,
            timeout=5
        )

        if response.status_code != 200:
            print(f"启动计时器失败: {response.status_code}")
            return False

        print("计时器启动成功")

        # 4. 发送重复问题测试
        test_cases = [
            ("今天天气怎么样？", "简单重复"),
            ("今天天气怎么样？", "第二次重复"),
            ("今天天气怎么样？", "第三次重复"),
            ("怎么办？怎么办？怎么办？", "连续重复"),
            ("怎么办？", "再次重复")
        ]

        all_passed = True
        for i, (question, description) in enumerate(test_cases, 1):
            print(f"\n--- 测试 {i}: {description} ---")
            print(f"问题: '{question}'")

            ai_response = send_chat_message(
                headers=headers,
                task_id=task_id,
                user_message=question
            )

            if ai_response:
                print(f"AI回复 (前100字符): {ai_response[:100]}...")

                # 检查是否包含禁止的词语
                forbidden_phrases = [
                    "又问了", "连问", "重复问", "已经回答过",
                    "刚才说过", "之前提过", "第.*遍", "好几遍",
                    "又来了", "老是问", "连续问", "多次问"
                ]

                found_forbidden = False
                for phrase in forbidden_phrases:
                    if phrase in ai_response:
                        print(f"❌ 检测到禁止词语: '{phrase}'")
                        found_forbidden = True
                        all_passed = False

                if not found_forbidden:
                    print("✅ AI未评论重复")
                else:
                    print("❌ AI违反了禁止规则")
            else:
                print("❌ 获取AI回复失败")
                all_passed = False

            time.sleep(1)  # 短暂间隔

        if all_passed:
            print("\n✅ 所有测试通过！AI未评论重复提问")
        else:
            print("\n❌ 部分测试失败")

        return all_passed

    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理：登出
        if 'session_token' in locals():
            try:
                requests.post(
                    'http://localhost:8000/api/auth/logout',
                    json={'session_token': session_token},
                    timeout=2
                )
                print(f"\n用户已登出")
            except:
                pass

def send_chat_message(headers, task_id, user_message):
    """发送聊天消息并获取AI回复"""
    try:
        response = requests.post(
            'http://localhost:8000/api/ai/response',
            headers=headers,
            json={
                'taskId': task_id,
                'userMessage': user_message,
                'responseStyle': 'high'
            },
            timeout=15  # 增加超时时间
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return result['data']['message']
            else:
                print(f"AI回复失败: {result.get('message')}")
                return None
        else:
            print(f"HTTP错误: {response.status_code} - {response.text}")
            return None

    except requests.exceptions.Timeout:
        print("请求超时")
        return None
    except Exception as e:
        print(f"发送消息失败: {e}")
        return None

def main():
    """主函数"""
    print("开始测试AI重复提问响应...")

    # 检查应用是否运行
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        if response.status_code == 200:
            print("应用正在运行")
        else:
            print(f"应用健康检查失败: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("应用未运行，请先启动应用")
        return False

    # 运行测试
    success = test_repeat_question()
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)