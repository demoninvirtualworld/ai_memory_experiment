from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime
import hashlib
import secrets

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'ai-memory-experiment-secret-key'
app.config['DEBUG'] = True
app.config['JSON_AS_ASCII'] = False

CORS(app)

# 数据存储路径
DATA_DIR = 'data/users'
MEMORY_GROUPS = ['no_memory', 'short_memory', 'medium_memory', 'long_memory']


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
        'submitted_at': None
    }
    user_data['task_set'].append(new_task_set)
    return new_task_set


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


# AI响应API - 简化版本，使用模拟回复（需要认证）
@app.route('/api/ai/response', methods=['POST'])
def get_ai_response():
    """获取AI回复（模拟版本）"""
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

    try:
        memory_group = user_data['memory_group']

        # 模拟AI回复 - 根据任务阶段和记忆组别生成不同的回复
        memory_indicators = {
            'no_memory': "（无记忆模式）",
            'short_memory': "（短期记忆）",
            'medium_memory': "（中期记忆）",
            'long_memory': "（长期记忆）"
        }

        memory_indicator = memory_indicators.get(memory_group, "")

        # 根据任务阶段生成回复
        if task_id == 1:
            responses = [
                f"很高兴认识你！{memory_indicator} 请告诉我更多关于你自己的信息。",
                f"谢谢分享！{memory_indicator} 你平时喜欢做什么来放松？",
                f"听起来很有趣！{memory_indicator} 能多告诉我一些你的兴趣爱好吗？",
                f"我明白了。{memory_indicator} 最近有什么让你特别开心或者困扰的事情吗？"
            ]
        elif task_id == 2:
            if memory_group == 'no_memory':
                responses = ["我不记得我们之前的对话了，你能再告诉我一些关于你的事情吗？"]
            else:
                responses = [
                    f"想起我们上次聊天，你提到了一些事情，不知道后来怎么样了？{memory_indicator}",
                    f"再次见到你很高兴！最近有什么新进展吗？{memory_indicator}",
                    f"我记得你之前提到过一些事情，现在情况如何？{memory_indicator}"
                ]
        elif task_id == 3:
            if memory_group == 'no_memory':
                responses = ["请告诉我更多关于这个项目的信息，这样我可以给你更好的建议。"]
            else:
                responses = [
                    f"基于我对你的了解，我建议你考虑以下方案...{memory_indicator}",
                    f"考虑到你的个人情况，我觉得这个方向可能适合你...{memory_indicator}",
                    f"根据我们之前的交流，我为你制定了这个个性化计划...{memory_indicator}"
                ]
        elif task_id == 4:
            if memory_group == 'no_memory':
                responses = ["感谢这次的交流，再见！"]
            else:
                responses = [
                    f"这段时间的交流让我对你有了很多了解，这次告别让我有些舍不得。{memory_indicator}",
                    f"回顾我们的互动，我觉得我们建立了很好的连接。祝你一切顺利！{memory_indicator}",
                    f"从第一次对话到现在，我看到了你的成长和变化。很高兴能陪伴你这段旅程。{memory_indicator}"
                ]
        else:
            responses = [f"我明白你的意思。{memory_indicator} 能告诉我更多细节吗？"]

        import random
        ai_response = random.choice(responses)

        # 保存AI回复
        task_set = get_user_task_set(user_data, task_id)

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
        return jsonify({
            'success': False,
            'message': 'AI响应生成失败'
        })


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
    print("访问地址: http://localhost:3000")
    print(f"数据存储目录: {DATA_DIR}")
    print("默认管理员账户: admin/psy2025")
    app.run(debug=True, port=3000, host='0.0.0.0')