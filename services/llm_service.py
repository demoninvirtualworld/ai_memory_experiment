"""
LLM 服务层 (LLM Service)

封装各 LLM API 调用：
- QwenManager: 通义千问 API
- DeepSeekManager: DeepSeek API

支持：
- 普通请求 (generate_response)
- 流式请求 (generate_response_stream)
- 要义摘要生成 (generate_summary)
"""

import json
import requests
from typing import List, Dict


class QwenManager:
    """通义千问 API 管理器"""

    def __init__(self, api_key: str, base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
                 model: str = "qwen-plus"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_response(self, messages: List[Dict], max_tokens: int = 2000, temperature: float = 0.8) -> str:
        """调用通义千问 API 生成回复"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"通义千问 API 错误: {response.status_code} - {response.text}")
                return "抱歉，我暂时无法回复。请稍后再试。"

        except Exception as e:
            print(f"调用通义千问 API 失败: {e}")
            return "网络错误，请检查连接后重试。"

    def generate_response_stream(self, messages: List[Dict], max_tokens: int = 2000, temperature: float = 0.8):
        """调用通义千问 API 生成流式回复（生成器）"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60,
                stream=True
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            else:
                print(f"通义千问 API 错误: {response.status_code} - {response.text}")
                yield "抱歉，我暂时无法回复。请稍后再试。"

        except Exception as e:
            print(f"调用通义千问 API 失败: {e}")
            yield "网络错误，请检查连接后重试。"

    def generate_summary(self, conversation: str, max_chars: int = 500) -> str:
        """
        生成对话要义摘要 (Gist Summary)

        基于 Fuzzy Trace Theory，将 Verbatim (字面信息) 转化为 Gist (语义要义)

        Args:
            conversation: 对话文本
            max_chars: 摘要最大字数限制

        Returns:
            要义摘要文本
        """
        try:
            system_prompt = f"""你是一个专业的对话分析助手。请将以下对话历史压缩为{max_chars}字以内的要义摘要。

要求：
1. 保留核心语义和用户意图，去除具体措辞和表面细节
2. 提取用户画像特征（性格特点、兴趣偏好、关注领域）
3. 记录重要事件、情感状态和关键决定
4. 使用第三人称描述（如"用户是..."、"用户曾提到..."）
5. 突出对后续对话有价值的信息

输出格式：
- 直接输出摘要内容，不要添加标题或序号
- 语言简洁，信息密度高
- 严格控制在{max_chars}字以内"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"对话历史：\n\n{conversation}"}
            ]

            # 估算需要的 token 数（中文约 1.5 token/字）
            max_tokens = int(max_chars * 1.5) + 100

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,  # 低温度保证输出稳定
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                summary = result['choices'][0]['message']['content']
                # 确保不超过字数限制
                if len(summary) > max_chars:
                    summary = summary[:max_chars] + "..."
                return summary
            else:
                print(f"通义千问摘要生成错误: {response.status_code}")
                return self._generate_fallback_summary(conversation, max_chars)

        except Exception as e:
            print(f"生成摘要失败: {e}")
            return self._generate_fallback_summary(conversation, max_chars)

    def _generate_fallback_summary(self, conversation: str, max_chars: int = 500) -> str:
        """
        备用摘要生成（降级方案）

        当 LLM API 不可用时，使用规则提取关键信息
        """
        lines = conversation.split('\n')
        user_lines = [line[3:].strip() for line in lines if line.startswith('用户：') and len(line) > 15]

        if not user_lines:
            return ""

        # 提取关键信息
        # 取前几条和后几条用户发言
        if len(user_lines) > 5:
            key_lines = user_lines[:3] + user_lines[-2:]
        else:
            key_lines = user_lines

        summary = "用户曾提到：" + "；".join(key_lines)

        # 限制字数
        if len(summary) > max_chars:
            summary = summary[:max_chars - 3] + "..."

        return summary

    def evaluate_importance(self, content: str, is_user_message: bool = True) -> float:
        """
        评估消息的重要性分数

        使用规则+启发式方法快速评估（避免每条消息都调用 LLM）

        Args:
            content: 消息内容
            is_user_message: 是否为用户消息

        Returns:
            重要性分数 (0.0 - 1.0)
        """
        return estimate_importance_score(content, is_user_message)


class DeepSeekManager:
    """DeepSeek API 管理器"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def generate_response(self, messages: List[Dict], max_tokens: int = 2000, temperature: float = 1.5) -> str:
        """调用DeepSeek API生成回复"""
        try:
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"DeepSeek API错误: {response.status_code} - {response.text}")
                return "抱歉，我暂时无法回复。请稍后再试。"

        except Exception as e:
            print(f"调用DeepSeek API失败: {e}")
            return "网络错误，请检查连接后重试。"

    def generate_response_stream(self, messages: List[Dict], max_tokens: int = 2000, temperature: float = 1.5):
        """调用DeepSeek API生成流式回复（生成器）"""
        try:
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30,
                stream=True
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            else:
                print(f"DeepSeek API错误: {response.status_code} - {response.text}")
                yield "抱歉，我暂时无法回复。请稍后再试。"

        except Exception as e:
            print(f"调用DeepSeek API失败: {e}")
            yield "网络错误，请检查连接后重试。"

    def generate_summary(self, conversation: str, max_chars: int = 500) -> str:
        """
        生成对话要义摘要 (Gist Summary)

        基于 Fuzzy Trace Theory，将 Verbatim (字面信息) 转化为 Gist (语义要义)

        Args:
            conversation: 对话文本
            max_chars: 摘要最大字数限制

        Returns:
            要义摘要文本
        """
        try:
            system_prompt = f"""你是一个专业的对话分析助手。请将以下对话历史压缩为{max_chars}字以内的要义摘要。

要求：
1. 保留核心语义和用户意图，去除具体措辞和表面细节
2. 提取用户画像特征（性格特点、兴趣偏好、关注领域）
3. 记录重要事件、情感状态和关键决定
4. 使用第三人称描述（如"用户是..."、"用户曾提到..."）
5. 突出对后续对话有价值的信息

输出格式：
- 直接输出摘要内容，不要添加标题或序号
- 语言简洁，信息密度高
- 严格控制在{max_chars}字以内"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"对话历史：\n\n{conversation}"}
            ]

            # 估算需要的 token 数（中文约 1.5 token/字）
            max_tokens = int(max_chars * 1.5) + 100

            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3,  # 低温度保证输出稳定
                "stream": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                summary = result['choices'][0]['message']['content']
                # 确保不超过字数限制
                if len(summary) > max_chars:
                    summary = summary[:max_chars] + "..."
                return summary
            else:
                print(f"DeepSeek摘要生成错误: {response.status_code}")
                return self._generate_fallback_summary(conversation, max_chars)

        except Exception as e:
            print(f"生成摘要失败: {e}")
            return self._generate_fallback_summary(conversation, max_chars)

    def _generate_fallback_summary(self, conversation: str, max_chars: int = 500) -> str:
        """
        备用摘要生成（降级方案）

        当 LLM API 不可用时，使用规则提取关键信息
        """
        lines = conversation.split('\n')
        user_lines = [line[3:].strip() for line in lines if line.startswith('用户：') and len(line) > 15]

        if not user_lines:
            return ""

        # 取前几条和后几条用户发言
        if len(user_lines) > 5:
            key_lines = user_lines[:3] + user_lines[-2:]
        else:
            key_lines = user_lines

        summary = "用户曾提到：" + "；".join(key_lines)

        # 限制字数
        if len(summary) > max_chars:
            summary = summary[:max_chars - 3] + "..."

        return summary

    def evaluate_importance(self, content: str, is_user_message: bool = True) -> float:
        """
        评估消息的重要性分数

        Args:
            content: 消息内容
            is_user_message: 是否为用户消息

        Returns:
            重要性分数 (0.0 - 1.0)
        """
        return estimate_importance_score(content, is_user_message)


# ============ 重要性评估工具函数 ============

def estimate_importance_score(content: str, is_user_message: bool = True) -> float:
    """
    基于规则估算消息重要性分数

    评估维度：
    1. 内容长度 - 较长的消息通常包含更多信息
    2. 情感词汇 - 包含情感表达的消息更重要
    3. 个人信息 - 包含个人信息的消息更重要
    4. 问题/请求 - 包含问题或请求的消息更重要
    5. 关键词密度 - 包含关键主题词的消息更重要

    Args:
        content: 消息内容
        is_user_message: 是否为用户消息

    Returns:
        重要性分数 (0.0 - 1.0)
    """
    if not content or not content.strip():
        return 0.0

    score = 0.3  # 基础分

    # 1. 内容长度评分 (0 - 0.2)
    length = len(content)
    if length > 200:
        score += 0.2
    elif length > 100:
        score += 0.15
    elif length > 50:
        score += 0.1
    elif length > 20:
        score += 0.05

    # 2. 情感词汇检测 (0 - 0.15)
    emotion_words = [
        '喜欢', '讨厌', '开心', '难过', '担心', '害怕', '期待', '失望',
        '兴奋', '焦虑', '感动', '生气', '伤心', '高兴', '烦恼', '压力',
        '爱', '恨', '感谢', '抱歉', '后悔', '希望', '梦想', '目标'
    ]
    emotion_count = sum(1 for word in emotion_words if word in content)
    score += min(0.15, emotion_count * 0.05)

    # 3. 个人信息检测 (0 - 0.15)
    personal_markers = [
        '我是', '我叫', '我的', '我想', '我觉得', '我认为', '我希望',
        '我喜欢', '我讨厌', '我工作', '我学', '我住', '我家',
        '岁', '年龄', '专业', '职业', '爱好', '兴趣'
    ]
    personal_count = sum(1 for marker in personal_markers if marker in content)
    score += min(0.15, personal_count * 0.05)

    # 4. 问题/请求检测 (0 - 0.1)
    if '?' in content or '？' in content:
        score += 0.05
    request_words = ['请', '帮', '能不能', '可以吗', '怎么', '如何', '为什么', '什么']
    if any(word in content for word in request_words):
        score += 0.05

    # 5. 重要主题词 (0 - 0.1)
    important_topics = [
        '计划', '决定', '选择', '问题', '困难', '挑战', '目标', '未来',
        '重要', '关键', '必须', '一定', '绝对', '永远', '从不'
    ]
    topic_count = sum(1 for topic in important_topics if topic in content)
    score += min(0.1, topic_count * 0.03)

    # 6. 用户消息通常比 AI 消息更重要
    if is_user_message:
        score += 0.1

    # 确保分数在 0-1 范围内
    return min(1.0, max(0.0, score))