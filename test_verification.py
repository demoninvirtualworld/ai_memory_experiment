#!/usr/bin/env python3
"""
验证AI记忆实验平台的测试脚本
测试五个记忆组别的基本功能
"""

import json
import requests
import sys
from typing import Dict, Optional

BASE_URL = "http://localhost:8000"

class MemoryTestClient:
    def __init__(self):
        self.session = requests.Session()
        self.tokens = {}
        self.users = {}

    def register_user(self, username: str, memory_group: str) -> bool:
        """注册测试用户"""
        data = {
            'username': username,
            'password': 'test123',
            'name': f'Test {memory_group}',
            'age': 25,
            'gender': 'male',
            'memory_group': memory_group,
            'ethics_consent_accepted': True
        }

        try:
            response = self.session.post(
                f"{BASE_URL}/api/auth/register",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                token = result['data']['session_token']
                self.tokens[memory_group] = token
                self.users[memory_group] = username
                print(f"[OK] 注册成功: {username} ({memory_group})")
                return True
            else:
                print(f"[FAIL] 注册失败 {username}: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[FAIL] 注册异常 {username}: {e}")
            return False

    def login(self, username: str, password: str = 'test123') -> Optional[str]:
        """登录用户"""
        data = {
            'username': username,
            'password': password
        }

        try:
            response = self.session.post(
                f"{BASE_URL}/api/auth/login",
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return result['data']['session_token']
            else:
                print(f"✗ 登录失败 {username}: {response.status_code}")
                return None

        except Exception as e:
            print(f"✗ 登录异常 {username}: {e}")
            return None

    def get_current_user(self, token: str) -> Optional[dict]:
        """获取当前用户信息"""
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = self.session.get(
                f"{BASE_URL}/api/users/me",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()['data']
            else:
                print(f"✗ 获取用户信息失败: {response.status_code}")
                return None

        except Exception as e:
            print(f"✗ 获取用户信息异常: {e}")
            return None

    def get_current_task(self, token: str) -> Optional[dict]:
        """获取当前任务"""
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = self.session.get(
                f"{BASE_URL}/api/users/me/tasks/current",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()['data']
            else:
                print(f"✗ 获取任务失败: {response.status_code}")
                return None

        except Exception as e:
            print(f"✗ 获取任务异常: {e}")
            return None

    def start_task(self, token: str, task_id: int) -> bool:
        """启动任务计时器"""
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = self.session.post(
                f"{BASE_URL}/api/users/me/tasks/{task_id}/start",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ 任务{task_id}启动成功")
                return True
            else:
                print(f"✗ 任务启动失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 任务启动异常: {e}")
            return False

    def send_message(self, token: str, task_id: int, user_message: str, response_style: str = 'high') -> Optional[str]:
        """发送消息获取AI回复"""
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = {
            'taskId': task_id,
            'userMessage': user_message,
            'responseStyle': response_style
        }

        try:
            response = self.session.post(
                f"{BASE_URL}/api/ai/response",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result['data']['message']
            else:
                print(f"✗ AI回复失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"✗ AI回复异常: {e}")
            return None

    def get_task_messages(self, token: str, task_id: int) -> Optional[list]:
        """获取任务聊天记录"""
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = self.session.get(
                f"{BASE_URL}/api/users/me/tasks/{task_id}/chats",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()['data']
            else:
                print(f"✗ 获取聊天记录失败: {response.status_code}")
                return None

        except Exception as e:
            print(f"✗ 获取聊天记录异常: {e}")
            return None

def main():
    print("=" * 60)
    print("AI记忆实验平台验证测试")
    print("=" * 60)

    client = MemoryTestClient()

    # 1. 注册五个记忆组别的用户
    print("\n1. 注册测试用户...")
    memory_groups = [
        'sensory_memory',
        'working_memory',
        'gist_memory',
        'perfect_recall_memory',
        'hybrid_memory'
    ]

    for group in memory_groups:
        username = f"test_{group}"
        client.register_user(username, group)

    print(f"\n注册完成，已创建 {len(client.tokens)} 个测试用户")

    # 2. 测试登录和用户信息获取
    print("\n2. 测试登录和用户信息...")
    for group, token in client.tokens.items():
        user_info = client.get_current_user(token)
        if user_info:
            print(f"✓ {group}: ID={user_info['id']}, 记忆组={user_info['memory_group']}")

    # 3. 测试任务系统
    print("\n3. 测试任务系统...")
    test_group = 'sensory_memory'
    token = client.tokens.get(test_group)

    if token:
        # 获取当前任务
        task = client.get_current_task(token)
        if task:
            print(f"✓ 当前任务: {task['title']} (ID: {task['id']})")

            # 启动任务
            task_id = task['id']
            if client.start_task(token, task_id):
                # 测试对话
                print(f"\n4. 测试{test_group}对话功能...")

                # 发送第一条消息
                message1 = "你好！我是测试用户，今天天气不错。"
                response1 = client.send_message(token, task_id, message1)
                if response1:
                    print(f"✓ 用户: {message1}")
                    print(f"✓ AI回复: {response1[:100]}...")

                    # 发送第二条消息测试记忆
                    message2 = "你还记得我刚才说了什么吗？"
                    response2 = client.send_message(token, task_id, message2)
                    if response2:
                        print(f"\n✓ 用户: {message2}")
                        print(f"✓ AI回复: {response2[:150]}...")

                        # 获取聊天记录
                        messages = client.get_task_messages(token, task_id)
                        if messages:
                            print(f"\n✓ 聊天记录: {len(messages)} 条消息")
                            for msg in messages:
                                role = "用户" if msg['is_user'] else "AI"
                                print(f"  {role}: {msg['content'][:50]}...")

    # 4. 测试不同记忆组别的差异
    print("\n5. 测试不同记忆组别的初始对话...")
    test_message = "你好，我是测试用户，我喜欢爬山和读书。"

    for group in ['sensory_memory', 'working_memory', 'gist_memory']:
        token = client.tokens.get(group)
        if token:
            task = client.get_current_task(token)
            if task:
                task_id = task['id']
                client.start_task(token, task_id)  # 确保任务启动
                response = client.send_message(token, task_id, test_message)
                if response:
                    print(f"\n{group}:")
                    print(f"  用户: {test_message}")
                    print(f"  AI回复摘要: {response[:100]}...")

    print("\n" + "=" * 60)
    print("验证测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()