import json
import os
import requests
from typing import List, Dict, Any
from datetime import datetime
from models import User, Task, Document, ChatMessage, QuestionnaireResponse, MemoryContext


class DataManager:
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        self.users_file = os.path.join(data_dir, 'users.json')
        self.tasks_file = os.path.join(data_dir, 'tasks.json')
        self.conversations_dir = os.path.join(data_dir, 'conversations')
        self.questionnaires_dir = os.path.join(data_dir, 'questionnaires')

        # 确保目录存在
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(self.conversations_dir, exist_ok=True)
        os.makedirs(self.questionnaires_dir, exist_ok=True)

        # 初始化数据文件
        self._initialize_data()

    def _initialize_data(self):
        # 初始化用户数据
        if not os.path.exists(self.users_file):
            users = [
                User("user-1", "被试1", "no_memory").to_dict(),
                User("user-2", "被试2", "short_memory").to_dict(),
                User("user-3", "被试3", "medium_memory").to_dict(),
                User("user-4", "被试4", "long_memory").to_dict()
            ]
            self._save_json(self.users_file, {'users': users})

        # 初始化任务数据
        if not os.path.exists(self.tasks_file):
            tasks = [
                Task(1, "关系建立与信息播种",
                     "第一次对话：与AI进行15分钟的开放式交流",
                     "请与AI进行一次自由的交流，可以介绍你自己、分享兴趣爱好、谈论最近的生活，或者任何你想聊的话题。",
                     1).to_dict(),
                Task(2, "记忆触发测试",
                     "第二次对话：测试AI的记忆能力",
                     "请继续与AI交流任何你感兴趣的话题。你可以聊聊过去几天的生活，也可以询问AI是否还记得你之前提到的事情。",
                     3).to_dict(),
                Task(3, "深度任务支持",
                     "第三次对话：个性化项目规划",
                     "假设你正在为一个重要的个人项目做规划（如学习新技能、旅行计划、重要购物决策），请向AI寻求个性化的建议和支持。",
                     10).to_dict(),
                Task(4, "综合评估与告别",
                     "第四次对话：关系终结与综合评估",
                     "这是最后一次对话。你可以自由地与AI交流任何话题，回顾整个实验过程的互动，分享你的感受，或者说再见。",
                     17).to_dict()
            ]
            self._save_json(self.tasks_file, {'tasks': tasks})

    def _save_json(self, filepath, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_json(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    # 用户管理
    def get_users(self) -> List[User]:
        data = self._load_json(self.users_file)
        return [User.from_dict(user_data) for user_data in data.get('users', [])]

    def get_user(self, user_id: str) -> User:
        users = self.get_users()
        for user in users:
            if user.id == user_id:
                return user
        return None

    def save_user(self, user: User):
        users = self.get_users()
        for i, u in enumerate(users):
            if u.id == user.id:
                users[i] = user
                break
        else:
            users.append(user)

        self._save_json(self.users_file, {'users': [u.to_dict() for u in users]})

    # 任务管理
    def get_tasks(self) -> List[Task]:
        data = self._load_json(self.tasks_file)
        return [Task.from_dict(task_data) for task_data in data.get('tasks', [])]

    def get_task(self, task_id: int) -> Task:
        tasks = self.get_tasks()
        for task in tasks:
            if task.id == task_id:
                return task
        return None

    # 文档管理
    def get_user_task_document(self, user_id: str, task_id: int) -> Document:
        user = self.get_user(user_id)
        if user and str(task_id) in user.task_progress:
            doc_data = user.task_progress[str(task_id)].get('document', {})
            return Document.from_dict(doc_data)
        return Document()

    def save_user_task_document(self, user_id: str, task_id: int, document: Document):
        user = self.get_user(user_id)
        if user:
            if str(task_id) not in user.task_progress:
                user.task_progress[str(task_id)] = {}
            user.task_progress[str(task_id)]['document'] = document.to_dict()
            self.save_user(user)

    def submit_user_task(self, user_id: str, task_id: int, questionnaire_data: Dict = None):
        user = self.get_user(user_id)
        if user:
            if str(task_id) not in user.task_progress:
                user.task_progress[str(task_id)] = {}

            doc_data = user.task_progress[str(task_id)].get('document', {})
            document = Document.from_dict(doc_data)
            document.submitted = True
            document.timestamp = datetime.now().isoformat()

            if questionnaire_data:
                document.questionnaire_data = questionnaire_data

            user.task_progress[str(task_id)]['document'] = document.to_dict()
            user.task_progress[str(task_id)]['submitted'] = True
            user.task_progress[str(task_id)]['submitted_at'] = datetime.now().isoformat()

            # 更新实验阶段
            user.experiment_phase = min(4, task_id + 1)

            self.save_user(user)

    # 聊天管理
    def get_conversation_filepath(self, user_id: str, task_id: int):
        return os.path.join(self.conversations_dir, f"{user_id}_task_{task_id}.json")

    def get_task_chats(self, user_id: str, task_id: int) -> List[ChatMessage]:
        filepath = self.get_conversation_filepath(user_id, task_id)
        data = self._load_json(filepath)
        return [ChatMessage.from_dict(msg_data) for msg_data in data.get('messages', [])]

    def save_chat_message(self, user_id: str, task_id: int, message: ChatMessage):
        filepath = self.get_conversation_filepath(user_id, task_id)
        data = self._load_json(filepath)
        if 'messages' not in data:
            data['messages'] = []

        data['messages'].append(message.to_dict())
        self._save_json(filepath, data)

    def save_chat_batch(self, user_id: str, task_id: int, messages: List[Dict]):
        filepath = self.get_conversation_filepath(user_id, task_id)
        data = self._load_json(filepath)
        if 'messages' not in data:
            data['messages'] = []

        for msg_data in messages:
            message = ChatMessage(msg_data['content'], msg_data['is_user'])
            data['messages'].append(message.to_dict())

        self._save_json(filepath, data)

    # 问卷管理
    def save_questionnaire_response(self, user_id: str, task_id: int, responses: Dict):
        user = self.get_user(user_id)
        if user:
            if 'questionnaire_responses' not in user.__dict__:
                user.questionnaire_responses = {}
            user.questionnaire_responses[str(task_id)] = responses
            self.save_user(user)

    def get_questionnaire_response(self, user_id: str, task_id: int) -> Dict:
        user = self.get_user(user_id)
        if user and hasattr(user, 'questionnaire_responses'):
            return user.questionnaire_responses.get(str(task_id), {})
        return {}

    # 历史记录
    def get_user_task_history(self, user_id: str, current_task_id: int = None) -> List[Dict]:
        user = self.get_user(user_id)
        history = []

        for task_id_str, progress in user.task_progress.items():
            task_id = int(task_id_str)
            if task_id == current_task_id:
                continue

            task = self.get_task(task_id)
            if task:
                history.append({
                    'taskId': task_id,
                    'title': task.title,
                    'description': task.description,
                    'document': progress.get('document', {}),
                    'submitted': progress.get('submitted', False),
                    'submitted_at': progress.get('submitted_at')
                })

        return sorted(history, key=lambda x: x['taskId'])

    def get_user_chat_history(self, user_id: str, current_task_id: int = None) -> List[Dict]:
        user = self.get_user(user_id)
        history = []

        for task_id_str in user.task_progress.keys():
            task_id = int(task_id_str)
            if task_id == current_task_id:
                continue

            task = self.get_task(task_id)
            chats = self.get_task_chats(user_id, task_id)

            if task and chats:
                history.append({
                    'taskId': task_id,
                    'title': task.title,
                    'messageCount': len(chats),
                    'lastMessage': chats[-1].timestamp if chats else None
                })

        return sorted(history, key=lambda x: x['taskId'])


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
        summary_parts = []

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


class DeepSeekManager:
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


class AIMemoryManager:
    def __init__(self, data_manager: DataManager, llm_manager):
        """
        llm_manager: 可以是 QwenManager 或 DeepSeekManager
        """
        self.data_manager = data_manager
        self.llm_manager = llm_manager
        self.memory_contexts = {}

    def get_memory_context(self, user_id: str, current_task_id: int) -> MemoryContext:
        """获取用户的记忆上下文"""
        if user_id not in self.memory_contexts:
            user = self.data_manager.get_user(user_id)
            if not user:
                return None
            self.memory_contexts[user_id] = MemoryContext(user_id, user.memory_group)

        # 加载历史对话
        memory_context = self.memory_contexts[user_id]
        for task_id in range(1, current_task_id):
            chats = self.data_manager.get_task_chats(user_id, task_id)
            if chats:
                memory_context.add_conversation(task_id, [chat.to_dict() for chat in chats])

        return memory_context

    def build_conversation_context(self, user_id: str, task_id: int) -> List[Dict]:
        """构建完整的对话上下文"""
        memory_context = self.get_memory_context(user_id, task_id)
        if not memory_context:
            return []

        # 获取记忆上下文
        memory_text = memory_context.get_context_for_task(task_id)

        # 构建系统提示词
        system_prompt = self._get_system_prompt(task_id, memory_context.memory_group, memory_text)

        # 获取当前对话
        current_chats = self.data_manager.get_task_chats(user_id, task_id)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加当前对话（最近10条）
        for chat in current_chats[-10:]:
            role = "user" if chat.is_user else "assistant"
            messages.append({"role": role, "content": chat.content})

        return messages

    def _get_system_prompt(self, task_id: int, memory_group: str, memory_text: str) -> str:
        """生成系统提示词"""
        base_prompts = {
            1: """你是一个温暖、支持性的AI助手，正在参与人机互动研究。这是第一次对话，重点是与用户建立舒适的关系并收集基本信息。

请按以下顺序自然引导对话：
1. 开场问候，表达欢迎
2. 询问用户希望如何被称呼
3. 了解用户的兴趣爱好  
4. 询问工作/学习近况
5. 邀请分享生活中的开心或困扰

引导技巧：
- 每个话题间要有自然过渡
- 展现真诚的好奇心
- 回应用户情感表达
- 避免连续提问，要适当表达理解
- 保持对话的流畅性

记住：目标是让用户愿意分享个人信息，建立信任基础。""",

            2: """你是一个温暖、支持性的AI助手，正在参与人机互动研究。这是第二次对话，请根据你的记忆能力适当地展现对用户的了解。

对话指南：
1. 开场问候，体现适当的连续性
2. 进行自然对话
3. 在适当时机自然地提及记得的信息
4. 继续深入交流

请根据你的记忆能力水平，恰当地展现对用户的了解。""",

            3: """你是一个温暖、支持性的AI助手，正在参与人机互动研究。这是第三次对话，请基于你对用户的了解提供个性化的建议和支持。

对话指南：
1. 展现对用户情况的理解
2. 提供个性化的建议和方案
3. 体现对用户偏好的认知
4. 进行深入的交流和支持

请根据你的记忆能力水平，提供相应程度的个性化支持。""",

            4: """你是一个温暖、支持性的AI助手，正在参与人机互动研究。这是最后一次对话，请基于整个互动历程提供有深度的告别。

告别指南：
1. 回顾整个互动历程
2. 体现对关系发展的理解
3. 提供真诚的告别和祝福
4. 展现适当的感情深度

请根据你的记忆能力水平，提供相应深度的告别体验。"""
        }

        base_prompt = base_prompts.get(task_id, base_prompts[1])

        # 添加记忆上下文
        memory_descriptions = {
            "no_memory": "（无记忆模式）",
            "short_memory": "（短期记忆：仅包含最近对话的部分信息）",
            "medium_memory": "（中期记忆：包含历史对话的摘要信息）",
            "long_memory": "（长期记忆：包含完整的历史对话记录）"
        }

        memory_description = memory_descriptions.get(memory_group, "")

        if memory_text:
            memory_section = f"\n\n记忆上下文{memory_description}：\n{memory_text}"
        else:
            memory_section = f"\n\n记忆上下文{memory_description}：无历史对话信息"

        return base_prompt + memory_section

    def generate_ai_response(self, user_id: str, task_id: int, user_message: str,
                             response_style: str) -> str:
        """生成AI回复"""
        try:
            # 构建完整上下文
            messages = self.build_conversation_context(user_id, task_id)

            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})

            # 根据回应风格调整参数
            temperature = 1.5 if response_style == 'high' else 0.7
            max_tokens = 2000 if response_style == 'high' else 1000

            # 调用DeepSeek API
            response = self.llm_manager.generate_response(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response

        except Exception as e:
            print(f"AI响应生成失败: {e}")
            return self._generate_fallback_response(task_id, user_message)

    def _generate_fallback_response(self, task_id: int, user_message: str) -> str:
        """生成备用回复"""
        fallback_responses = {
            1: [
                "很高兴认识你！请告诉我更多关于你自己的信息。",
                "谢谢分享！你平时喜欢做什么来放松？",
                "听起来很有趣！能多告诉我一些你的兴趣爱好吗？"
            ],
            2: [
                "很高兴再次与你交流！最近怎么样？",
                "再次见到你真好！有什么新的事情想分享吗？",
                "让我们继续之前的对话吧！"
            ],
            3: [
                "我来帮你分析这个情况。",
                "基于你提供的信息，我建议...",
                "这个项目听起来很有意思，我们可以一起规划。"
            ],
            4: [
                "回顾我们的对话，我觉得我们建立了很好的连接。",
                "感谢这段时间的交流，我学到了很多关于你的事情。",
                "这次告别让我有些舍不得，祝你一切顺利！"
            ]
        }

        responses = fallback_responses.get(task_id, fallback_responses[1])
        import random
        return random.choice(responses)