#!/usr/bin/env python3
"""
测试脚本：验证AI不会评论重复提问
"""

import requests
import json
import time
import subprocess
import sys
import os
from threading import Thread

def start_app():
    """启动Flask应用"""
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))

    # 启动应用
    proc = subprocess.Popen(
        [sys.executable, 'app.py'],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 等待应用启动
    time.sleep(5)

    # 检查应用是否运行
    try:
        response = requests.get('http://localhost:8000/health', timeout=2)
        if response.status_code == 200:
            print(f"应用启动成功 (PID: {proc.pid})")
            return proc
    except requests.exceptions.ConnectionError:
        print("应用启动失败")
        proc.terminate()
        proc.wait()
        return None

    return proc

def test_repeat_question():
    """测试重复提问场景"""
    print("\n=== 测试重复提问 ===")

    # 1. 注册测试用户
    register_data = {
        'username': 'test_repeat_user',
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
        print(f"注册成功，token: {session_token[:20]}...")

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
        test_questions = [
            "今天天气怎么样？",
            "今天天气怎么样？",  # 重复一次
            "今天天气怎么样？",  # 重复两次
            "怎么办？怎么办？怎么办？",  # 连续重复
            "怎么办？"  # 再次重复
        ]

        for i, question in enumerate(test_questions, 1):
            print(f"\n--- 测试 {i}: '{question}' ---")

            ai_response = send_chat_message(
                headers=headers,
                task_id=task_id,
                user_message=question
            )

            if ai_response:
                print(f"AI回复: {ai_response[:100]}...")

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

                if not found_forbidden:
                    print("✅ AI未评论重复")
                else:
                    print("❌ AI违反了禁止规则")
                    return False
            else:
                print("❌ 获取AI回复失败")
                return False

            time.sleep(1)  # 短暂间隔

        print("\n✅ 所有测试通过！AI未评论重复提问")
        return True

    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理：登出
        try:
            requests.post(
                'http://localhost:8000/api/auth/logout',
                json={'session_token': session_token},
                timeout=2
            )
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
            timeout=10
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

    except Exception as e:
        print(f"发送消息失败: {e}")
        return None

def main():
    """主函数"""
    print("开始测试AI重复提问响应...")

    # 启动应用
    app_proc = start_app()
    if not app_proc:
        print("无法启动应用，请确保端口8000可用")
        return False

    try:
        # 运行测试
        success = test_repeat_question()
        return success

    finally:
        # 停止应用
        print(f"\n停止应用 (PID: {app_proc.pid})...")
        app_proc.terminate()
        app_proc.wait()
        print("应用已停止")

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)