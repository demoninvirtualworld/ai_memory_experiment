#!/usr/bin/env python3
"""
直接测试 DeepSeek API
使用用户提供的 API 密钥
"""

import sys
import io
from services.llm_service import DeepSeekManager

def safe_print(text, end='\n'):
    """安全打印，处理编码错误"""
    try:
        print(text, end=end)
    except UnicodeEncodeError:
        # 替换无法编码的字符
        encoded = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
        print(encoded, end=end)

def test_deepseek_api(api_key: str, base_url: str = "https://api.deepseek.com/v1"):
    """测试 DeepSeek API"""
    safe_print("=" * 50)
    safe_print("DeepSeek API 测试")
    safe_print("=" * 50)
    safe_print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    safe_print(f"Base URL: {base_url}")
    safe_print("")

    # 初始化 DeepSeek 管理器
    try:
        manager = DeepSeekManager(api_key=api_key, base_url=base_url)
        safe_print("[OK] DeepSeekManager 初始化成功")
    except Exception as e:
        safe_print(f"[FAIL] DeepSeekManager 初始化失败: {e}")
        return False

    # 测试生成回复
    safe_print("\n1. 测试简单对话...")
    messages = [
        {"role": "system", "content": "你是一个友好的助手。"},
        {"role": "user", "content": "你好！请用中文介绍一下你自己。"}
    ]

    try:
        response = manager.generate_response(
            messages=messages,
            max_tokens=500,
            temperature=0.8
        )
        safe_print(f"[OK] API 调用成功")
        safe_print(f"回复: {response[:200]}...")
    except Exception as e:
        safe_print(f"[FAIL] API 调用失败: {e}")
        return False

    # 测试流式回复
    safe_print("\n2. 测试流式回复...")
    try:
        stream_result = ""
        for chunk in manager.generate_response_stream(
            messages=messages,
            max_tokens=200,
            temperature=0.8
        ):
            stream_result += chunk
            safe_print(f"流式块: {chunk}", end="")

        safe_print(f"\n[OK] 流式回复完成")
        safe_print(f"完整回复: {stream_result[:100]}...")
    except Exception as e:
        safe_print(f"[FAIL] 流式回复失败: {e}")
        # 流式回复失败不影响整体测试

    # 测试摘要生成
    safe_print("\n3. 测试摘要生成...")
    conversation = """用户：你好！我是小明，今年25岁，是一名软件工程师。
AI：你好小明！很高兴认识你。软件工程师这个职业很有意思呢，你主要做什么方向的开发？
用户：我主要做后端开发，用Python和Go语言。最近在做一个AI相关的项目。
AI：AI项目啊，听起来很有挑战性！是什么样的项目呢？
用户：是一个关于记忆的实验平台，研究AI如何记住对话历史。"""

    try:
        summary = manager.generate_summary(
            conversation=conversation,
            max_chars=200
        )
        safe_print(f"[OK] 摘要生成成功")
        safe_print(f"摘要: {summary}")
    except Exception as e:
        safe_print(f"[FAIL] 摘要生成失败: {e}")

    safe_print("\n" + "=" * 50)
    safe_print("DeepSeek API 测试完成")
    safe_print("=" * 50)
    return True

def main():
    # 使用用户提供的 API 密钥
    api_key = "sk-3221b81cd40245ed92dd80b2bce1d3d6"

    if len(sys.argv) > 1:
        api_key = sys.argv[1]

    if not api_key:
        safe_print("错误: 需要提供 API 密钥")
        safe_print("用法: python test_deepseek_direct.py [api_key]")
        sys.exit(1)

    success = test_deepseek_api(api_key)

    if success:
        safe_print("\n[SUCCESS] 所有测试通过！DeepSeek API 工作正常。")
    else:
        safe_print("\n[FAILURE] 测试失败，请检查 API 密钥和网络连接。")
        sys.exit(1)

if __name__ == "__main__":
    main()