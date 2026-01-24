from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os
import json
from datetime import datetime, timedelta
import hashlib
import secrets

from config import Config
from utils import QwenManager, DeepSeekManager, AIMemoryManager, DataManager
from models import MemoryContext

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'ai-memory-experiment-secret-key'
app.config['DEBUG'] = True
app.config['JSON_AS_ASCII'] = False

CORS(app)

# 数据存储路径
DATA_DIR = 'data/users'
# 新的四级记忆架构（基于认知心理学理论）
MEMORY_GROUPS = ['sensory_memory', 'working_memory', 'gist_memory', 'hybrid_memory']
# 旧版本记忆组映射（向后兼容）
LEGACY_MEMORY_MAPPING = {
    'no_memory': 'sensory_memory',
    'short_memory': 'working_memory',
    'medium_memory': 'gist_memory',
    'long_memory': 'hybrid_memory',
}

# 初始化大模型管理器
experiment_config = Config.EXPERIMENT_CONFIG
if experiment_config['model_provider'] == 'qwen':
    llm_manager = QwenManager(
        api_key=experiment_config['qwen_api_key'],
        base_url=experiment_config['qwen_base_url'],
        model=experiment_config['qwen_model']
    )
    print(f"使用通义千问模型: {experiment_config['qwen_model']}")
else:
    llm_manager = DeepSeekManager(
        api_key=experiment_config['deepseek_api_key'],
        base_url=experiment_config['deepseek_base_url']
    )
    print("使用 DeepSeek 模型")

# 初始化数据管理器和记忆管理器
data_manager = DataManager('data')
ai_memory_manager = AIMemoryManager(data_manager, llm_manager)


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


def ensure_data_dir():
    """确保数据目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def get_user_file_path(user_id):
    """获取用户数据文件路径"""
    return os.path.join(DATA_DIR, f'{user_id}.json')


def user_exists(user_id):
    """检查用户是否存在"""
    return os.path.exists(get_user_file_path(user_id))


def load_user_data(user_id):
    """加载用户数据"""
    file_path = get_user_file_path(user_id)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_user_data(user_data):
    """保存用户数据"""
    user_id = user_data['user_id']
    file_path = get_user_file_path(user_id)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)


def get_all_users():
    """获取所有用户列表"""
    ensure_data_dir()
    users = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            user_id = filename[:-5]  # 去掉.json后缀
            user_data = load_user_data(user_id)
            if user_data:
                users.append(user_data)
    return users


def hash_password(password):
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token():
    """生成会话令牌"""
    return secrets.token_hex(32)


def get_user_task_set(user_data, task_id):
    """获取用户的任务集，如果不存在则创建"""
    if 'task_set' not in user_data:
        user_data['task_set'] = []

    for task_set in user_data['task_set']:
        if task_set['task_id'] == task_id:
            return task_set

    # 如果不存在，创建新的任务集
    new_task_set = {
        'task_id': task_id,
        'conversation': [],
        'questionnaire': [],
        'document': {
            'title': '',
            'content': '',
            'submitted': False,
            'timestamp': datetime.now().isoformat()
        },
        'submitted': False,
        'submitted_at': None,
        'timer': {
            'started_at': None,      # 任务开始时间
            'end_time': None,        # 任务结束时间（开始后15分钟）
            'duration': 15 * 60,     # 持续时间（秒）
            'is_expired': False      # 是否已超时
        }
    }
    user_data['task_set'].append(new_task_set)
    return new_task_set


def check_task_timer(task_set):
    """检查任务计时器是否超时"""
    timer = task_set.get('timer', {})

    # 如果没有计时器信息，返回未超时
    if not timer.get('end_time'):
        return False

    # 解析结束时间
    try:
        end_time = datetime.fromisoformat(timer['end_time'])
        now = datetime.now()

        # 检查是否超时
        is_expired = now >= end_time

        # 更新超时状态
        if is_expired and not timer.get('is_expired'):
            timer['is_expired'] = True

        return is_expired
    except:
        return False


def initialize_data():
    """初始化任务数据"""
    global tasks_data
    tasks_data = {
        1: Task(1, "关系建立与信息播种",
                "第一次对话：与AI进行15分钟的开放式交流",
                "请与AI进行一次自由的交流，可以介绍你自己、分享兴趣爱好、谈论最近的生活，或者任何你想聊的话题。",
                1),
        2: Task(2, "记忆触发测试",
                "第二次对话：测试AI的记忆能力",
                "请继续与AI交流任何你感兴趣的话题。你可以聊聊过去几天的生活，也可以询问AI是否还记得你之前提到的事情。",
                3),
        3: Task(3, "深度任务支持",
                "第三次对话：个性化项目规划",
                "假设你正在为一个重要的个人项目做规划（如学习新技能、旅行计划、重要购物决策），请向AI寻求个性化的建议和支持。",
                10),
        4: Task(4, "综合评估与告别",
                "第四次对话：关系终结与综合评估",
                "这是最后一次对话。你可以自由地与AI交流任何话题，回顾整个实验过程的互动，分享你的感受，或者说再见。",
                17)
    }


def create_default_admin():
    """创建默认管理员账户"""
    admin_id = 'admin'
    if not user_exists(admin_id):
        admin_user = {
            'user_id': admin_id,
            'username': admin_id,
            'name': '系统管理员',
            'age': 30,
            'gender': 'male',
            'memory_group': 'no_memory',
            'user_type': 'admin',
            'password_hash': hash_password('psy2025'),  # 默认密码
            'settings': {
                'responseStyle': 'high',
                'aiAvatar': 'human'
            },
            'created_at': datetime.now().isoformat(),
            'demographics': {},
            'experiment_phase': 1,
            'task_set': []
        }
        save_user_data(admin_user)
        print("默认管理员账户已创建: admin/psy2025")


# 会话存储（生产环境应该用Redis等）
active_sessions = {}

# 初始化数据
ensure_data_dir()
initialize_data()
create_default_admin()  # 创建默认管理员


# 静态文件服务
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


# API路由
@app.route('/api/system/config', methods=['GET'])
def get_system_config():
    """获取系统配置"""
    return jsonify({
        'success': True,
        'data': {
            'countdownTime': 15 * 60,  # 15分钟
            'memoryGroups': MEMORY_GROUPS,
            'experimentPhases': 4
        }
    })


# 认证相关API
@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    age = data.get('age')
    gender = data.get('gender')
    memory_group = data.get('memory_group', 'no_memory')

    if not all([username, password, name, age, gender]):
        return jsonify({'success': False, 'message': '请填写所有必填字段'})

    if memory_group not in MEMORY_GROUPS:
        return jsonify({'success': False, 'message': '无效的记忆组别'})

    # 检查用户是否已存在
    if user_exists(username):
        return jsonify({'success': False, 'message': '用户名已存在'})

    # 创建新用户（只能是普通用户）
    new_user = {
        'user_id': username,
        'username': username,
        'name': name,
        'age': age,
        'gender': gender,
        'memory_group': memory_group,
        'user_type': 'normal',  # 固定为普通用户
        'password_hash': hash_password(password),
        'settings': {
            'responseStyle': 'high',
            'aiAvatar': 'human'
        },
        'created_at': datetime.now().isoformat(),
        'demographics': {},
        'experiment_phase': 1,
        'task_set': []
    }

    save_user_data(new_user)

    # 创建会话
    session_token = generate_session_token()
    active_sessions[session_token] = {
        'user_id': username,
        'login_time': datetime.now().isoformat()
    }

    return jsonify({
        'success': True,
        'data': {
            'session_token': session_token,
            'user': {
                'id': username,
                'username': username,
                'name': name,
                'age': age,
                'gender': gender,
                'memory_group': memory_group,
                'user_type': 'normal',  # 固定为普通用户
                'settings': new_user['settings'],
                'created_at': new_user['created_at'],
                'experiment_phase': new_user['experiment_phase']
            }
        }
    })


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({'success': False, 'message': '请填写用户名和密码'})

    user_data = load_user_data(username)
    if not user_data:
        return jsonify({'success': False, 'message': '用户不存在'})

    if user_data['password_hash'] != hash_password(password):
        return jsonify({'success': False, 'message': '密码错误'})

    # 创建会话
    session_token = generate_session_token()
    active_sessions[session_token] = {
        'user_id': username,
        'login_time': datetime.now().isoformat()
    }

    return jsonify({
        'success': True,
        'data': {
            'session_token': session_token,
            'user': {
                'id': user_data['user_id'],
                'username': user_data['username'],
                'name': user_data['name'],
                'age': user_data['age'],
                'gender': user_data['gender'],
                'memory_group': user_data['memory_group'],
                'user_type': user_data.get('user_type', 'normal'),
                'settings': user_data.get('settings', {}),
                'created_at': user_data.get('created_at'),
                'experiment_phase': user_data.get('experiment_phase', 1)
            }
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    data = request.get_json()
    session_token = data.get('session_token')

    if session_token in active_sessions:
        del active_sessions[session_token]

    return jsonify({'success': True})


def get_user_from_session(request):
    """从会话中获取用户"""
    session_token = request.headers.get('Authorization')
    if not session_token or not session_token.startswith('Bearer '):
        return None

    session_token = session_token[7:]  # 去掉 'Bearer ' 前缀
    session = active_sessions.get(session_token)
    if not session:
        return None

    return load_user_data(session['user_id'])


# 用户相关API（需要认证）
@app.route('/api/users/me', methods=['GET'])
def get_current_user():
    """获取当前用户信息"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    return jsonify({
        'success': True,
        'data': {
            'id': user_data['user_id'],
            'username': user_data['username'],
            'name': user_data['name'],
            'age': user_data['age'],
            'gender': user_data['gender'],
            'memory_group': user_data['memory_group'],
            'user_type': user_data.get('user_type', 'normal'),
            'settings': user_data.get('settings', {}),
            'created_at': user_data.get('created_at'),
            'experiment_phase': user_data.get('experiment_phase', 1)
        }
    })


@app.route('/api/users/me/settings', methods=['POST'])
def update_current_user_settings():
    """更新当前用户设置"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.get_json()
    settings = data.get('settings', {})

    user_data['settings'].update(settings)
    save_user_data(user_data)

    return jsonify({'success': True})


# 任务相关API（需要认证）
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    tasks = [task.to_dict() for task in tasks_data.values()]
    return jsonify({
        'success': True,
        'data': tasks
    })


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    task = tasks_data.get(task_id)
    if task:
        return jsonify({
            'success': True,
            'data': task.to_dict()
        })
    else:
        return jsonify({'success': False, 'message': '任务不存在'})


@app.route('/api/users/me/tasks/current', methods=['GET'])
def get_current_task():
    """获取当前用户的下一个任务（普通用户按顺序获取）"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 如果是管理员，返回空
    if user_data.get('user_type') == 'admin':
        return jsonify({
            'success': True,
            'data': None
        })

    # 获取下一个未完成的任务
    completed_tasks = [ts['task_id'] for ts in user_data.get('task_set', []) if ts.get('submitted', False)]

    # 按任务ID顺序查找第一个未完成的任务
    for task_id in sorted(tasks_data.keys()):
        if task_id not in completed_tasks:
            current_task = tasks_data[task_id]
            return jsonify({
                'success': True,
                'data': current_task.to_dict()
            })

    # 如果所有任务都完成了
    return jsonify({
        'success': True,
        'data': None
    })


@app.route('/api/users/me/tasks/<int:task_id>/document', methods=['GET'])
def get_task_document(task_id):
    """获取用户任务文档"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    task_set = get_user_task_set(user_data, task_id)
    return jsonify({
        'success': True,
        'data': task_set.get('document', {
            'title': '',
            'content': '',
            'submitted': False,
            'timestamp': datetime.now().isoformat()
        })
    })


@app.route('/api/users/me/tasks/<int:task_id>/document', methods=['POST'])
def save_task_document(task_id):
    """保存用户任务文档"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.get_json()
    task_set = get_user_task_set(user_data, task_id)
    task_set['document'] = {
        'title': data.get('title', ''),
        'content': data.get('content', ''),
        'submitted': False,
        'timestamp': datetime.now().isoformat(),
        'questionnaire_data': {}
    }
    save_user_data(user_data)

    return jsonify({'success': True})


@app.route('/api/users/me/tasks/<int:task_id>/start', methods=['POST'])
def start_task_timer(task_id):
    """启动任务计时器"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    task_set = get_user_task_set(user_data, task_id)
    timer = task_set.get('timer', {})

    # 如果已经启动过，返回现有的计时器信息
    if timer.get('started_at'):
        return jsonify({
            'success': True,
            'data': {
                'started_at': timer['started_at'],
                'end_time': timer['end_time'],
                'duration': timer['duration'],
                'is_expired': check_task_timer(task_set)
            }
        })

    # 首次启动，初始化计时器
    now = datetime.now()
    duration = 15 * 60  # 15分钟

    timer['started_at'] = now.isoformat()
    timer['end_time'] = (now + timedelta(seconds=duration)).isoformat()
    timer['duration'] = duration
    timer['is_expired'] = False

    task_set['timer'] = timer
    save_user_data(user_data)

    return jsonify({
        'success': True,
        'data': {
            'started_at': timer['started_at'],
            'end_time': timer['end_time'],
            'duration': timer['duration'],
            'is_expired': False
        }
    })


@app.route('/api/users/me/tasks/<int:task_id>/timer', methods=['GET'])
def get_task_timer(task_id):
    """获取任务计时器状态"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    task_set = get_user_task_set(user_data, task_id)
    timer = task_set.get('timer', {})

    # 检查是否超时
    is_expired = check_task_timer(task_set)

    # 如果状态有变化，保存
    if is_expired and not timer.get('is_expired'):
        timer['is_expired'] = True
        save_user_data(user_data)

    return jsonify({
        'success': True,
        'data': {
            'started_at': timer.get('started_at'),
            'end_time': timer.get('end_time'),
            'duration': timer.get('duration', 15 * 60),
            'is_expired': is_expired
        }
    })


@app.route('/api/users/me/tasks/<int:task_id>/submit', methods=['POST'])
def submit_task(task_id):
    """提交任务"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.get_json()
    questionnaire_data = data.get('questionnaire_data', {})

    task_set = get_user_task_set(user_data, task_id)

    # 更新文档状态
    if 'document' in task_set:
        task_set['document']['submitted'] = True
        task_set['document']['questionnaire_data'] = questionnaire_data

    task_set['submitted'] = True
    task_set['submitted_at'] = datetime.now().isoformat()

    # 更新实验阶段
    user_data['experiment_phase'] = min(4, task_id + 1)

    save_user_data(user_data)
    return jsonify({'success': True})


@app.route('/api/users/me/tasks/history', methods=['GET'])
def get_task_history():
    """获取用户任务历史"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    history = []
    for task_set in user_data.get('task_set', []):
        task_id = task_set['task_id']
        task = tasks_data.get(task_id)
        if task:
            history.append({
                'taskId': task_id,
                'title': task.title,
                'description': task.description,
                'document': task_set.get('document', {}),
                'submitted': task_set.get('submitted', False),
                'submitted_at': task_set.get('submitted_at')
            })

    return jsonify({
        'success': True,
        'data': sorted(history, key=lambda x: x['taskId'])
    })


# 聊天相关API（需要认证）
@app.route('/api/users/me/tasks/<int:task_id>/chats', methods=['GET'])
def get_task_chats(task_id):
    """获取任务聊天记录"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    task_set = get_user_task_set(user_data, task_id)
    return jsonify({
        'success': True,
        'data': task_set.get('conversation', [])
    })


@app.route('/api/users/me/tasks/<int:task_id>/chats', methods=['POST'])
def save_chat_message(task_id):
    """保存聊天消息"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.get_json()
    task_set = get_user_task_set(user_data, task_id)

    if 'conversation' not in task_set:
        task_set['conversation'] = []

    message = {
        'message_id': f"msg_{datetime.now().timestamp()}",
        'content': data['content'],
        'is_user': data['isUser'],
        'timestamp': datetime.now().isoformat()
    }

    task_set['conversation'].append(message)
    save_user_data(user_data)

    return jsonify({'success': True})


@app.route('/api/users/me/chats/history', methods=['GET'])
def get_chat_history():
    """获取用户聊天历史"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    history = []
    for task_set in user_data.get('task_set', []):
        task_id = task_set['task_id']
        task = tasks_data.get(task_id)
        conversation = task_set.get('conversation', [])

        if task and conversation:
            history.append({
                'taskId': task_id,
                'title': task.title,
                'messageCount': len(conversation),
                'lastMessage': conversation[-1]['timestamp'] if conversation else None
            })

    return jsonify({
        'success': True,
        'data': sorted(history, key=lambda x: x['taskId'])
    })


# AI响应API - 使用真正的大模型（需要认证）
@app.route('/api/ai/response', methods=['POST'])
def get_ai_response():
    """获取AI回复（调用通义千问/DeepSeek）"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 管理员不与AI交互
    if user_data.get('user_type') == 'admin':
        return jsonify({'success': False, 'message': '管理员用户不能与AI交互'}), 403

    data = request.get_json()

    task_id = data.get('taskId')
    user_message = data.get('userMessage')
    response_style = data.get('responseStyle', 'high')

    if not all([task_id, user_message]):
        return jsonify({'success': False, 'message': '缺少必要参数'})

    # 检查任务计时器是否超时
    task_set = get_user_task_set(user_data, task_id)
    if check_task_timer(task_set):
        return jsonify({'success': False, 'message': '对话时间已结束'}), 403

    try:
        user_id = user_data['user_id']
        memory_group = user_data['memory_group']

        # 处理旧版本记忆组名称
        if memory_group in LEGACY_MEMORY_MAPPING:
            memory_group = LEGACY_MEMORY_MAPPING[memory_group]

        # 获取历史对话，构建记忆上下文
        memory_context = MemoryContext(user_id, memory_group, llm_manager=llm_manager)

        # 加载该用户所有之前任务的对话
        for prev_task_id in range(1, task_id):
            prev_task_set = None
            for ts in user_data.get('task_set', []):
                if ts['task_id'] == prev_task_id:
                    prev_task_set = ts
                    break
            if prev_task_set and prev_task_set.get('conversation'):
                memory_context.add_conversation(prev_task_id, prev_task_set['conversation'])

        # 设置当前查询（用于混合记忆的相关性检索）
        memory_context.set_current_query(user_message)

        # 获取记忆上下文文本
        memory_text = memory_context.get_context_for_task(task_id)

        # 构建系统提示词
        system_prompt = build_system_prompt(task_id, memory_group, memory_text)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加当前任务的对话历史
        task_set = get_user_task_set(user_data, task_id)
        current_conversation = task_set.get('conversation', [])

        # 取最近10条消息
        for msg in current_conversation[-10:]:
            role = "user" if msg.get('is_user', False) else "assistant"
            messages.append({"role": role, "content": msg['content']})

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 根据回应风格调整参数
        temperature = 0.9 if response_style == 'high' else 0.6
        max_tokens = 2000 if response_style == 'high' else 1000

        # 调用大模型 API
        ai_response = llm_manager.generate_response(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # 保存AI回复
        if 'conversation' not in task_set:
            task_set['conversation'] = []

        ai_message = {
            'message_id': f"msg_{datetime.now().timestamp()}",
            'content': ai_response,
            'is_user': False,
            'timestamp': datetime.now().isoformat()
        }

        task_set['conversation'].append(ai_message)
        save_user_data(user_data)

        return jsonify({
            'success': True,
            'data': {
                'message': ai_response
            }
        })

    except Exception as e:
        print(f"AI响应错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'AI响应生成失败: {str(e)}'
        })


def build_system_prompt(task_id: int, memory_group: str, memory_text: str) -> str:
    """构建系统提示词"""
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

    # 根据记忆组别添加不同的指令（新的四级认知架构）
    memory_instructions = {
        # L1: 感觉记忆 - 无编码，信息未进入意识
        "sensory_memory": (
            "\n\n【记忆模式：感觉记忆】你没有任何关于用户的记忆，每次对话都是全新的开始。"
            "你无法记住任何之前的对话内容，请不要假装记得。"
            "如果用户提到'之前说过'，请诚实地表示你不记得。"
        ),

        # L2: 工作记忆 - Miller 7±2 组块
        "working_memory": (
            "\n\n【记忆模式：工作记忆】你只能记住最近几轮的对话内容（约7轮）。"
            "更早的对话内容已经从你的记忆中消失。"
            "请基于这些有限的近期记忆与用户交流，如果用户提到更早的事情，你可能不记得了。"
        ),

        # L3: 要义记忆 - Verbatim -> Gist
        "gist_memory": (
            "\n\n【记忆模式：要义记忆】你记得之前对话的大致内容和要点，但不一定记得具体的措辞。"
            "你了解用户的基本情况和主要话题，但具体细节可能模糊。"
            "这就像人类的自然记忆一样——记得'聊过什么'但不一定记得'原话怎么说'。"
        ),

        # L4: 混合记忆 - 短时焦点 + 长时检索
        "hybrid_memory": (
            "\n\n【记忆模式：混合记忆】你拥有两种记忆能力："
            "(1) 清晰记得最近的对话内容；"
            "(2) 能够回想起与当前话题相关的历史细节。"
            "当用户提到某个话题时，相关的过往记忆会被唤醒。"
            "请充分利用这些记忆，展现对用户的深度了解。"
        )
    }

    # 兼容旧版本记忆组名称
    legacy_mapping = {
        "no_memory": "sensory_memory",
        "short_memory": "working_memory",
        "medium_memory": "gist_memory",
        "long_memory": "hybrid_memory",
    }

    # 获取记忆指令
    if memory_group in memory_instructions:
        memory_instruction = memory_instructions[memory_group]
    elif memory_group in legacy_mapping:
        memory_instruction = memory_instructions[legacy_mapping[memory_group]]
    else:
        memory_instruction = ""

    # 添加记忆上下文
    if memory_text:
        memory_section = f"\n\n=== 历史记忆 ===\n{memory_text}\n=== 记忆结束 ==="
    else:
        memory_section = ""

    return base_prompt + memory_instruction + memory_section


# AI流式响应API - 使用Server-Sent Events（需要认证）
@app.route('/api/ai/response/stream', methods=['POST'])
def get_ai_response_stream():
    """获取AI流式回复（调用通义千问/DeepSeek流式API）"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 管理员不与AI交互
    if user_data.get('user_type') == 'admin':
        return jsonify({'success': False, 'message': '管理员用户不能与AI交互'}), 403

    data = request.get_json()

    task_id = data.get('taskId')
    user_message = data.get('userMessage')
    response_style = data.get('responseStyle', 'high')

    if not all([task_id, user_message]):
        return jsonify({'success': False, 'message': '缺少必要参数'})

    # 检查任务计时器是否超时
    task_set = get_user_task_set(user_data, task_id)
    if check_task_timer(task_set):
        return jsonify({'success': False, 'message': '对话时间已结束'}), 403

    def generate():
        try:
            user_id = user_data['user_id']
            memory_group = user_data['memory_group']

            # 处理旧版本记忆组名称
            if memory_group in LEGACY_MEMORY_MAPPING:
                memory_group = LEGACY_MEMORY_MAPPING[memory_group]

            # 获取历史对话，构建记忆上下文
            memory_context = MemoryContext(user_id, memory_group, llm_manager=llm_manager)

            # 加载该用户所有之前任务的对话
            for prev_task_id in range(1, task_id):
                prev_task_set = None
                for ts in user_data.get('task_set', []):
                    if ts['task_id'] == prev_task_id:
                        prev_task_set = ts
                        break
                if prev_task_set and prev_task_set.get('conversation'):
                    memory_context.add_conversation(prev_task_id, prev_task_set['conversation'])

            # 设置当前查询（用于混合记忆的相关性检索）
            memory_context.set_current_query(user_message)

            # 获取记忆上下文文本
            memory_text = memory_context.get_context_for_task(task_id)

            # 构建系统提示词
            system_prompt = build_system_prompt(task_id, memory_group, memory_text)

            # 构建消息列表
            messages = [{"role": "system", "content": system_prompt}]

            # 添加当前任务的对话历史
            task_set = get_user_task_set(user_data, task_id)
            current_conversation = task_set.get('conversation', [])

            # 取最近10条消息
            for msg in current_conversation[-10:]:
                role = "user" if msg.get('is_user', False) else "assistant"
                messages.append({"role": role, "content": msg['content']})

            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})

            # 根据回应风格调整参数
            temperature = 0.9 if response_style == 'high' else 0.6
            max_tokens = 2000 if response_style == 'high' else 1000

            # 收集完整回复用于保存
            full_response = ""

            # 调用大模型流式API
            for chunk in llm_manager.generate_response_stream(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            ):
                full_response += chunk
                # 发送SSE格式的数据
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            # 发送结束信号
            yield f"data: {json.dumps({'done': True})}\n\n"

            # 保存完整的AI回复
            if 'conversation' not in task_set:
                task_set['conversation'] = []

            ai_message = {
                'message_id': f"msg_{datetime.now().timestamp()}",
                'content': full_response,
                'is_user': False,
                'timestamp': datetime.now().isoformat()
            }

            task_set['conversation'].append(ai_message)
            save_user_data(user_data)

        except Exception as e:
            print(f"AI流式响应错误: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': f'AI响应生成失败: {str(e)}'})}\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')


# 问卷相关API（需要认证）
@app.route('/api/users/me/tasks/<int:task_id>/questionnaire', methods=['POST'])
def save_questionnaire(task_id):
    """保存问卷数据"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    data = request.get_json()
    responses = data.get('responses', {})

    task_set = get_user_task_set(user_data, task_id)
    task_set['questionnaire'] = responses
    save_user_data(user_data)

    return jsonify({'success': True})


# 实验管理API（需要认证）
@app.route('/api/experiment/progress', methods=['GET'])
def get_experiment_progress():
    """获取实验进度"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    completed_tasks = sum(1 for task_set in user_data.get('task_set', []) if task_set.get('submitted', False))
    total_tasks = 4

    return jsonify({
        'success': True,
        'data': {
            'completed_tasks': completed_tasks,
            'total_tasks': total_tasks,
            'progress_percentage': (completed_tasks / total_tasks) * 100,
            'current_phase': user_data.get('experiment_phase', 1)
        }
    })


# 管理员API
@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    """管理员获取所有用户列表"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 检查用户权限
    if user_data.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    all_users_data = get_all_users()
    users = []
    for user in all_users_data:
        # 只返回普通用户
        if user.get('user_type') == 'normal':
            completed_tasks = sum(1 for task_set in user.get('task_set', []) if task_set.get('submitted', False))
            users.append({
                'id': user['user_id'],
                'username': user['username'],
                'name': user['name'],
                'age': user['age'],
                'gender': user['gender'],
                'memory_group': user['memory_group'],
                'created_at': user.get('created_at'),
                'experiment_phase': user.get('experiment_phase', 1),
                'completed_tasks': completed_tasks,
                'total_tasks': 4
            })

    return jsonify({
        'success': True,
        'data': users
    })


@app.route('/api/admin/users/<user_id>', methods=['GET'])
def admin_get_user(user_id):
    """管理员获取指定用户详细信息"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 检查用户权限
    if user_data.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    target_user = load_user_data(user_id)
    if not target_user:
        return jsonify({'success': False, 'message': '用户不存在'})

    # 只允许查看普通用户
    if target_user.get('user_type') != 'normal':
        return jsonify({'success': False, 'message': '只能查看普通用户'})

    return jsonify({
        'success': True,
        'data': target_user
    })


@app.route('/api/admin/users/<user_id>/progress', methods=['POST'])
def admin_update_user_progress(user_id):
    """管理员更新用户进度"""
    user_data = get_user_from_session(request)
    if not user_data:
        return jsonify({'success': False, 'message': '未登录'}), 401

    # 检查用户权限
    if user_data.get('user_type') != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    target_user = load_user_data(user_id)
    if not target_user:
        return jsonify({'success': False, 'message': '用户不存在'})

    # 只允许修改普通用户
    if target_user.get('user_type') != 'normal':
        return jsonify({'success': False, 'message': '只能修改普通用户'})

    data = request.get_json()
    experiment_phase = data.get('experiment_phase')
    task_progress = data.get('task_progress', {})

    if experiment_phase is not None:
        target_user['experiment_phase'] = min(4, max(1, experiment_phase))

    # 更新任务进度
    for task_id, progress in task_progress.items():
        task_set = get_user_task_set(target_user, int(task_id))
        if 'submitted' in progress:
            task_set['submitted'] = progress['submitted']
        if 'submitted_at' in progress:
            task_set['submitted_at'] = progress['submitted_at']

    save_user_data(target_user)

    return jsonify({'success': True})


# 重置实验数据（用于调试）
@app.route('/api/debug/reset', methods=['POST'])
def reset_data():
    """重置实验数据"""
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(DATA_DIR, filename)
            os.remove(file_path)

    # 清除活动会话
    active_sessions.clear()

    ensure_data_dir()
    # 重新创建默认管理员
    create_default_admin()
    return jsonify({'success': True})


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': '接口不存在'})


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': '服务器内部错误'})


if __name__ == '__main__':
    print("启动AI记忆能力实验平台...")
    print("访问地址: http://localhost:8000")
    print(f"数据存储目录: {DATA_DIR}")
    print("默认管理员账户: admin/psy2025")
    app.run(debug=True, port=8000, host='0.0.0.0')