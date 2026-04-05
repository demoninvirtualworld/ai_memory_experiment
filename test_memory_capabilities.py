#!/usr/bin/env python3
"""
测试五个记忆层级的记忆能力差异
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def login_user(username, password='test123'):
    """登录用户返回token"""
    data = {'username': username, 'password': password}
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json=data, timeout=10)
        if response.status_code == 200:
            return response.json()['data']['session_token']
        else:
            print(f"Login failed for {username}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Login error for {username}: {e}")
        return None

def get_user_info(token):
    """获取用户信息"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{BASE_URL}/api/users/me", headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()['data']
        else:
            return None
    except Exception as e:
        print(f"Get user info error: {e}")
        return None

def start_task(token, task_id):
    """启动任务"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.post(
            f"{BASE_URL}/api/users/me/tasks/{task_id}/start",
            headers=headers,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Start task error: {e}")
        return False

def send_message(token, task_id, user_message, response_style='high'):
    """发送消息并获取AI回复"""
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    data = {
        'taskId': task_id,
        'userMessage': user_message,
        'responseStyle': response_style
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/ai/response",
            headers=headers,
            json=data,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()['data']['message']
        else:
            print(f"Send message failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Send message error: {e}")
        return None

def test_memory_group(username, memory_group):
    """测试特定记忆组别的记忆能力"""
    print(f"\n{'='*60}")
    print(f"Testing {memory_group} (user: {username})")
    print(f"{'='*60}")

    # 登录
    token = login_user(username)
    if not token:
        print(f"Failed to login {username}")
        return False

    user_info = get_user_info(token)
    if not user_info:
        print("Failed to get user info")
        return False

    print(f"User group: {user_info['memory_group']}")

    # 获取任务
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{BASE_URL}/api/users/me/tasks/current", headers=headers, timeout=10)
    if response.status_code != 200:
        print("Failed to get current task")
        return False

    task = response.json()['data']
    if not task:
        print("No pending tasks")
        return False

    task_id = task['id']
    print(f"Task: {task_id} - {task['title']}")

    # 启动任务
    if not start_task(token, task_id):
        print("Failed to start task")
        return False

    # 测试对话序列
    test_cases = [
        ("第一轮：个人信息", "你好，我叫李华，今年28岁，是一名教师。"),
        ("第二轮：爱好", "我喜欢游泳和摄影，周末经常去公园拍照。"),
        ("第三轮：记忆测试1", "你还记得我的名字吗？"),
        ("第四轮：记忆测试2", "我刚才说我有什么爱好？"),
        ("第五轮：新信息", "我养了一只猫叫咪咪，它三岁了。"),
        ("第六轮：记忆测试3", "我的猫叫什么名字？"),
        ("第七轮：更多信息", "我最近在学习法语，打算明年去法国旅行。"),
        ("第八轮：记忆测试4", "你还记得我的职业是什么吗？"),
        ("第九轮：早期记忆测试", "你还记得我最开始说的名字吗？"),
    ]

    responses = []

    for i, (desc, message) in enumerate(test_cases, 1):
        print(f"\n{i}. {desc}")
        print(f"   User: {message}")

        response_text = send_message(token, task_id, message)
        if response_text:
            # 简化输出，只显示前100字符
            display_text = response_text[:150].replace('\n', ' ')
            print(f"   AI: {display_text}...")

            # 分析记忆关键词
            keywords = {
                '李华': '李华' in response_text,
                '教师': '教师' in response_text or '老师' in response_text,
                '游泳': '游泳' in response_text,
                '摄影': '摄影' in response_text or '拍照' in response_text,
                '猫': '猫' in response_text,
                '咪咪': '咪咪' in response_text,
                '法语': '法语' in response_text,
                '法国': '法国' in response_text,
            }

            detected = [k for k, v in keywords.items() if v]
            if detected:
                print(f"   Detected keywords: {detected}")

            responses.append((message, response_text, keywords))
        else:
            print(f"   No response received")
            responses.append((message, None, {}))

        # 短暂暂停避免速率限制
        time.sleep(1)

    # 分析记忆模式
    print(f"\n{'='*60}")
    print(f"Memory Analysis for {memory_group}")
    print(f"{'='*60}")

    # 检查关键记忆点
    memory_checkpoints = [
        ("Name recall (round 3)", 3, ['李华']),
        ("Hobby recall (round 4)", 4, ['游泳', '摄影']),
        ("Cat name recall (round 6)", 6, ['咪咪', '猫']),
        ("Profession recall (round 8)", 8, ['教师', '老师']),
        ("Early name recall (round 9)", 9, ['李华']),
    ]

    for checkpoint, round_num, expected_keywords in memory_checkpoints:
        if round_num - 1 < len(responses):
            _, response_text, keywords = responses[round_num - 1]
            if response_text:
                found = any(keywords.get(kw, False) for kw in expected_keywords)
                status = "REMEMBERED" if found else "FORGOTTEN"
                print(f"{checkpoint}: {status}")
            else:
                print(f"{checkpoint}: NO RESPONSE")
        else:
            print(f"{checkpoint}: NOT TESTED")

    return True

def main():
    print("Memory Capabilities Test")
    print("="*60)

    # 测试用户列表 (之前应该已注册)
    test_users = [
        ('test_sensory', 'sensory_memory'),
        ('test_working', 'working_memory'),
        ('test_gist', 'gist_memory'),
        ('test_perfect_recall', 'perfect_recall_memory'),
        ('test_hybrid', 'hybrid_memory'),
    ]

    # 由于时间限制，只测试前三个组别
    for username, group in test_users[:3]:
        test_memory_group(username, group)
        time.sleep(2)  # 组间暂停

if __name__ == "__main__":
    main()