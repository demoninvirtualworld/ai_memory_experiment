#!/usr/bin/env python3
"""
DeepSeek API 使用示例
演示如何使用 DeepSeekManager 生成回答
"""

import sys
sys.path.insert(0, '.')

from services.llm_service import DeepSeekManager

def safe_print(text, end='\n'):
    """安全打印，处理编码错误"""
    try:
        print(text, end=end)
    except UnicodeEncodeError:
        # 替换无法编码的字符
        encoded = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
        print(encoded, end=end)

def simple_chat():
    """简单对话示例"""
    # 使用您的 API 密钥
    api_key = "sk-3221b81cd40245ed92dd80b2bce1d3d6"

    # 初始化 DeepSeekManager
    manager = DeepSeekManager(api_key=api_key)

    # 构建对话消息
    messages = [
        {"role": "system", "content": "你是一个友好、乐于助人的助手。"},
        {"role": "user", "content": "你好！今天天气不错，你有什么建议的活动吗？"}
    ]

    safe_print("用户: 你好！今天天气不错，你有什么建议的活动吗？")

    # 生成回复
    response = manager.generate_response(
        messages=messages,
        max_tokens=500,
        temperature=0.8
    )

    safe_print(f"AI: {response}")

    # 继续对话
    messages.append({"role": "assistant", "content": response})
    messages.append({"role": "user", "content": "我还喜欢读书，你有什么推荐的书吗？"})

    safe_print("\n用户: 我还喜欢读书，你有什么推荐的书吗？")

    response2 = manager.generate_response(
        messages=messages,
        max_tokens=500,
        temperature=0.8
    )

    safe_print(f"AI: {response2}")

def generate_summary_example():
    """生成摘要示例"""
    api_key = "sk-3221b81cd40245ed92dd80b2bce1d3d6"
    manager = DeepSeekManager(api_key=api_key)

    conversation = """
    用户：我最近开始学习编程，感觉有点困难。
    AI：学习编程确实有挑战性，但坚持下去会有收获的。你在学什么语言？
    用户：我在学Python，觉得语法还好，但遇到问题不知道怎么解决。
    AI：遇到问题很正常。可以试试在Stack Overflow上搜索，或者加入一些编程社区。
    用户：好的，我会试试。我还想学习数据科学，不知道从哪里开始。
    AI：数据科学可以从Python的pandas和numpy库开始，然后学习机器学习基础。
    """

    summary = manager.generate_summary(
        conversation=conversation,
        max_chars=300
    )

    safe_print("对话摘要示例:")
    safe_print("=" * 50)
    safe_print("原始对话:")
    safe_print(conversation)
    safe_print("\n生成的摘要:")
    safe_print(summary)
    safe_print("=" * 50)

def main():
    safe_print("DeepSeek API 使用示例")
    safe_print("=" * 50)

    # 简单对话
    safe_print("\n1. 简单对话示例:")
    safe_print("-" * 30)
    simple_chat()

    # 摘要生成
    safe_print("\n\n2. 对话摘要示例:")
    safe_print("-" * 30)
    generate_summary_example()

    safe_print("\n示例完成！")

if __name__ == "__main__":
    main()