#!/usr/bin/env python3
"""
测试系统提示词生成
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

from app import build_system_prompt

def test_prompt():
    print("测试系统提示词生成...")
    print("=" * 80)

    # 测试任务1，感觉记忆组，无记忆文本
    prompt = build_system_prompt(1, 'sensory_memory', '')
    print(f"任务1，感觉记忆，无记忆文本：")
    print(f"提示词长度：{len(prompt)} 字符")
    print(f"前500字符：")
    print(prompt[:500])
    print("\n" + "=" * 80)

    # 检查是否包含自然对话指令
    if "【非常重要！禁止规则】" in prompt:
        print("[OK] 包含自然对话指令")
    else:
        print("[ERROR] 缺少自然对话指令")

    # 检查是否包含禁止重复规则
    if "绝对禁止指出重复" in prompt:
        print("[OK] 包含禁止重复规则")
    else:
        print("[ERROR] 缺少禁止重复规则")

    # 检查示例
    if "用户连续多次问" in prompt:
        print("[OK] 包含重复问题示例")
    else:
        print("[ERROR] 缺少重复问题示例")

    print("\n完整提示词（截断）：")
    print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)

    print("\n" + "=" * 80)

    # 测试任务5，混合记忆组，有记忆文本
    memory_text = "用户之前提到喜欢爬山，对海鲜过敏。"
    prompt2 = build_system_prompt(5, 'hybrid_memory', memory_text)
    print(f"\n任务5，混合记忆，有记忆文本：")
    print(f"提示词长度：{len(prompt2)} 字符")
    print(f"包含记忆文本：{memory_text}")

    # 检查记忆部分
    if "=== 历史记忆 ===" in prompt2:
        print("[OK] 包含历史记忆分隔符")
    else:
        print("[ERROR] 缺少历史记忆分隔符")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    test_prompt()