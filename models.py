import json
import os
from datetime import datetime
from typing import Dict, List, Any



class User:
    def __init__(self, user_id: str, name: str, memory_group: str):
        self.id = user_id
        self.name = name
        self.memory_group = memory_group
        self.settings = {
            'responseStyle': 'high',
            'aiAvatar': 'human'
        }
        self.current_task_id = None
        self.task_progress = {}
        self.created_at = datetime.now().isoformat()
        # 实验特定字段
        self.demographics = {}
        self.experiment_phase = 1  # 1-4阶段
        self.questionnaire_responses = {}

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'memory_group': self.memory_group,
            'settings': self.settings,
            'current_task_id': self.current_task_id,
            'task_progress': self.task_progress,
            'created_at': self.created_at,
            'demographics': self.demographics,
            'experiment_phase': self.experiment_phase,
            'questionnaire_responses': self.questionnaire_responses
        }

    @classmethod
    def from_dict(cls, data):
        user = cls(data['id'], data['name'], data['memory_group'])
        user.settings = data.get('settings', {})
        user.current_task_id = data.get('current_task_id')
        user.task_progress = data.get('task_progress', {})
        user.created_at = data.get('created_at')
        user.demographics = data.get('demographics', {})
        user.experiment_phase = data.get('experiment_phase', 1)
        user.questionnaire_responses = data.get('questionnaire_responses', {})
        return user


class Task:
    def __init__(self, task_id: int, title: str, description: str, content: str, time_point: int):
        self.id = task_id
        self.title = title
        self.description = description
        self.content = content
        self.time_point = time_point
        self.phase = self._get_phase(time_point)

    def _get_phase(self, time_point):
        phases = {
            1: "关系建立与信息播种",
            3: "记忆触发测试",
            10: "深度任务支持",
            17: "综合评估与告别"
        }
        return phases.get(time_point, "未知阶段")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'content': self.content,
            'time_point': self.time_point,
            'phase': self.phase
        }


class Document:
    def __init__(self, title: str = "", content: str = ""):
        self.title = title
        self.content = content
        self.submitted = False
        self.timestamp = datetime.now().isoformat()
        self.questionnaire_data = {}  # 存储问卷数据

    def to_dict(self):
        return {
            'title': self.title,
            'content': self.content,
            'submitted': self.submitted,
            'timestamp': self.timestamp,
            'questionnaire_data': self.questionnaire_data
        }

    @classmethod
    def from_dict(cls, data):
        doc = cls(data.get('title', ''), data.get('content', ''))
        doc.submitted = data.get('submitted', False)
        doc.timestamp = data.get('timestamp')
        doc.questionnaire_data = data.get('questionnaire_data', {})
        return doc


class ChatMessage:
    def __init__(self, content: str, is_user: bool, message_id: str = None):
        self.message_id = message_id or f"msg_{datetime.now().timestamp()}"
        self.content = content
        self.is_user = is_user
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            'message_id': self.message_id,
            'content': self.content,
            'is_user': self.is_user,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data):
        msg = cls(data['content'], data['is_user'], data['message_id'])
        msg.timestamp = data['timestamp']
        return msg


class QuestionnaireResponse:
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.responses = {}
        self.submitted_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'responses': self.responses,
            'submitted_at': self.submitted_at
        }

    @classmethod
    def from_dict(cls, data):
        response = cls(data['task_id'])
        response.responses = data.get('responses', {})
        response.submitted_at = data.get('submitted_at')
        return response


class MemoryContext:
    """记忆上下文管理"""

    def __init__(self, user_id: str, memory_group: str):
        self.user_id = user_id
        self.memory_group = memory_group
        self.conversation_history = []

    def add_conversation(self, task_id: int, conversation: List[Dict]):
        """添加对话记录"""
        self.conversation_history.append({
            'task_id': task_id,
            'conversation': conversation,
            'timestamp': datetime.now().isoformat()
        })

    def get_context_for_task(self, current_task_id: int, max_tokens: int = 128000):
        """获取当前任务的记忆上下文"""
        if self.memory_group == "no_memory":
            return self._get_no_memory_context()
        elif self.memory_group == "short_memory":
            return self._get_short_memory_context(current_task_id, max_tokens)
        elif self.memory_group == "medium_memory":
            return self._get_medium_memory_context(current_task_id, max_tokens)
        elif self.memory_group == "long_memory":
            return self._get_long_memory_context(current_task_id, max_tokens)
        else:
            return ""

    def _get_no_memory_context(self):
        """无记忆组上下文"""
        return ""

    def _get_short_memory_context(self, current_task_id: int, max_tokens: int):
        """短记忆组上下文"""
        if current_task_id <= 1:
            return ""

        previous_task_id = current_task_id - 1
        previous_conversation = self._get_conversation_by_task_id(previous_task_id)

        if not previous_conversation:
            return ""

        # 取后1/3的对话
        conversation_text = self._conversation_to_text(previous_conversation)
        lines = conversation_text.split('\n')
        if len(lines) <= 3:
            return conversation_text

        start_index = len(lines) * 2 // 3
        short_context = '\n'.join(lines[start_index:])

        return self._truncate_to_tokens(short_context, max_tokens)

    def _get_medium_memory_context(self, current_task_id: int, max_tokens: int):
        """中记忆组上下文"""
        previous_tasks = [task for task in self.conversation_history if task['task_id'] < current_task_id]

        if not previous_tasks:
            return ""

        # 生成摘要
        summaries = []
        for task_data in previous_tasks:
            conversation_text = self._conversation_to_text(task_data['conversation'])
            summary = self._generate_conversation_summary(conversation_text, task_data['task_id'])
            summaries.append(summary)

        full_summary = "\n\n".join(summaries)
        return self._truncate_to_tokens(full_summary, max_tokens)

    def _get_long_memory_context(self, current_task_id: int, max_tokens: int):
        """长记忆组上下文"""
        previous_tasks = [task for task in self.conversation_history if task['task_id'] < current_task_id]

        if not previous_tasks:
            return ""

        full_history = []
        for task_data in previous_tasks:
            conversation_text = self._conversation_to_text(task_data['conversation'])
            full_history.append(f"第{task_data['task_id']}次对话：\n{conversation_text}")

        combined_history = "\n\n".join(full_history)
        return self._truncate_to_tokens(combined_history, max_tokens)

    def _get_conversation_by_task_id(self, task_id: int):
        """根据任务ID获取对话"""
        for task_data in self.conversation_history:
            if task_data['task_id'] == task_id:
                return task_data['conversation']
        return None

    def _conversation_to_text(self, conversation: List[Dict]):
        """将对话列表转换为文本"""
        lines = []
        for msg in conversation:
            role = "用户" if msg.get('is_user', False) else "AI助手"
            lines.append(f"{role}：{msg.get('content', '')}")
        return "\n".join(lines)

    def _generate_conversation_summary(self, conversation: str, task_id: int):
        """生成对话摘要"""
        # 在实际实现中，这里应该调用大模型生成真正的摘要
        # 这里简化为提取关键信息
        lines = conversation.split('\n')
        key_lines = [line for line in lines if len(line.strip()) > 10]

        if len(key_lines) > 5:
            summary_lines = key_lines[:3] + ["..."] + key_lines[-2:]
        else:
            summary_lines = key_lines

        return f"第{task_id}次对话摘要：\n" + "\n".join(summary_lines)

    def _truncate_to_tokens(self, text: str, max_tokens: int):
        """截断文本到指定token数（简化版，按字符估算）"""
        # 简单估算：中文字符大致按1.5个token计算
        estimated_tokens = len(text) * 1.5

        if estimated_tokens <= max_tokens:
            return text

        # 截取前max_tokens/1.5个字符
        max_chars = int(max_tokens / 1.5)
        return text[:max_chars] + "...（内容已截断）"