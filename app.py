"""
AI 记忆能力实验平台 - Flask 应用

重构版本：使用 SQLite + 服务层架构
- database/: SQLAlchemy 数据层
- services/: 业务逻辑层 (MemoryEngine, TimerService)
"""

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import os
import json
from datetime import datetime
from functools import wraps

from config import Config
from services.llm_service import QwenManager, DeepSeekManager
from database import init_db, get_session, DBManager
from services import MemoryEngine, TimerService, ConsolidationService

# ============ Flask 应用初始化 ============

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DEBUG'] = Config.DEBUG
app.config['JSON_AS_ASCII'] = False

CORS(app)

# ============ 全局服务初始化 ============

# 数据库
DB_PATH = 'data/experiment.db'
engine, SessionLocal = init_db(DB_PATH)

# LLM 管理器
experiment_config = Config.EXPERIMENT_CONFIG
if experiment_config['model_provider'] == 'qwen':
    llm_manager = QwenManager(
        api_key=experiment_config['qwen_api_key'],
        base_url=experiment_config['qwen_base_url'],
        model=experiment_config['qwen_model']
    )
    print(f"[启动] 使用通义千问模型: {experiment_config['qwen_model']}")
else:
    llm_manager = DeepSeekManager(
        api_key=experiment_config['deepseek_api_key'],
        base_url=experiment_config['deepseek_base_url']
    )
    print("[启动] 使用 DeepSeek 模型")

# 会话存储（生产环境应使用 Redis）
active_sessions = {}

# 任务定义（静态数据）
TASKS_DATA = {
    1: {
        'id': 1,
        'title': '关系建立与信息播种',
        'description': '第一次对话：与AI进行15分钟的开放式交流',
        'content': '请与AI进行一次自由的交流，可以介绍你自己、分享兴趣爱好、谈论最近的生活，或者任何你想聊的话题。',
        'time_point': 1,
        'phase': '关系建立与信息播种'
    },
    2: {
        'id': 2,
        'title': '记忆触发测试',
        'description': '第二次对话：测试AI的记忆能力',
        'content': '请继续与AI交流任何你感兴趣的话题。你可以聊聊过去几天的生活，也可以询问AI是否还记得你之前提到的事情。',
        'time_point': 3,
        'phase': '记忆触发测试'
    },
    3: {
        'id': 3,
        'title': '深度任务支持',
        'description': '第三次对话：个性化项目规划',
        'content': '假设你正在为一个重要的个人项目做规划（如学习新技能、旅行计划、重要购物决策），请向AI寻求个性化的建议和支持。',
        'time_point': 10,
        'phase': '深度任务支持'
    },
    4: {
        'id': 4,
        'title': '综合评估与告别',
        'description': '第四次对话：关系终结与综合评估',
        'content': '这是最后一次对话。你可以自由地与AI交流任何话题，回顾整个实验过程的互动，分享你的感受，或者说再见。',
        'time_point': 17,
        'phase': '综合评估与告别'
    }
}

# 记忆组别
MEMORY_GROUPS = ['sensory_memory', 'working_memory', 'gist_memory', 'hybrid_memory']


# ============ 辅助函数 ============

def get_db():
    """获取数据库会话和管理器"""
    session = get_session(SessionLocal)
    return DBManager(session), session


def get_services():
    """获取所有服务实例"""
    db, session = get_db()
    memory_engine = MemoryEngine(db, llm_manager)
    timer_service = TimerService(db)
    return db, memory_engine, timer_service, session


def get_user_from_session(req):
    """从请求中获取当前用户"""
    auth_header = req.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, None

    token = auth_header[7:]
    session_data = active_sessions.get(token)
    if not session_data:
        return None, None

    db, db_session = get_db()
    user = db.get_user(session_data['user_id'])
    return user, db_session


def api_response(success=True, data=None, message=None, status=200):
    """统一的 API 响应格式"""
    response = {'success': success}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return jsonify(response), status


def require_auth(f):
    """认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user, session = get_user_from_session(request)
        if not user:
            return api_response(False, message='未登录', status=401)
        # 将 user 和 session 传递给路由函数
        return f(user, session, *args, **kwargs)
    return decorated


def require_admin(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user, session = get_user_from_session(request)
        if not user:
            return api_response(False, message='未登录', status=401)
        if user.user_type != 'admin':
            return api_response(False, message='权限不足', status=403)
        return f(user, session, *args, **kwargs)
    return decorated


# ============ 静态文件服务 ============

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)


# ============ 系统 API ============

@app.route('/api/system/config', methods=['GET'])
def get_system_config():
    """获取系统配置"""
    return api_response(True, data={
        'countdownTime': 15 * 60,
        'memoryGroups': MEMORY_GROUPS,
        'experimentPhases': 4
    })


@app.route('/api/debug', methods=['GET'])
def debug_status():
    """调试/健康检查接口"""
    db, session = get_db()
    try:
        # 测试数据库连接
        user_count = len(db.get_all_users())
        db_status = 'OK'
    except Exception as e:
        user_count = 0
        db_status = f'ERROR: {str(e)}'
    finally:
        session.close()

    # 测试 LLM 连接状态
    llm_status = 'OK' if llm_manager else 'NOT_CONFIGURED'

    return api_response(True, data={
        'status': 'running',
        'database': {
            'path': DB_PATH,
            'status': db_status,
            'user_count': user_count
        },
        'llm': {
            'provider': experiment_config['model_provider'],
            'status': llm_status
        },
        'sessions': len(active_sessions),
        'timestamp': datetime.now().isoformat()
    })


# ============ 认证 API ============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    age = data.get('age')
    gender = data.get('gender')
    memory_group = data.get('memory_group', 'sensory_memory')

    if not all([username, password, name, age, gender]):
        return api_response(False, message='请填写所有必填字段')

    if memory_group not in MEMORY_GROUPS:
        return api_response(False, message='无效的记忆组别')

    db, session = get_db()
    try:
        user = db.create_user(
            user_id=username,
            username=username,
            name=name,
            password=password,
            age=age,
            gender=gender,
            memory_group=memory_group,
            user_type='normal'
        )

        if not user:
            return api_response(False, message='用户名已存在')

        # 创建会话
        token = db.generate_session_token()
        active_sessions[token] = {
            'user_id': username,
            'login_time': datetime.now().isoformat()
        }

        # 记录登录日志
        db.log_event(username, 'register')

        return api_response(True, data={
            'session_token': token,
            'user': {
                'id': user.user_id,
                'username': user.username,
                'name': user.name,
                'age': user.age,
                'gender': user.gender,
                'memory_group': user.memory_group,
                'user_type': user.user_type,
                'settings': user.settings,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'experiment_phase': user.experiment_phase
            }
        })
    finally:
        session.close()


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return api_response(False, message='请填写用户名和密码')

    db, session = get_db()
    try:
        if not db.verify_password(username, password):
            return api_response(False, message='用户名或密码错误')

        user = db.get_user(username)

        # 创建会话
        token = db.generate_session_token()
        active_sessions[token] = {
            'user_id': username,
            'login_time': datetime.now().isoformat()
        }

        # 记录登录日志
        db.log_event(username, 'login')

        return api_response(True, data={
            'session_token': token,
            'user': {
                'id': user.user_id,
                'username': user.username,
                'name': user.name,
                'age': user.age,
                'gender': user.gender,
                'memory_group': user.memory_group,
                'user_type': user.user_type,
                'settings': user.settings or {},
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'experiment_phase': user.experiment_phase
            }
        })
    finally:
        session.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    data = request.get_json()
    token = data.get('session_token')

    if token in active_sessions:
        del active_sessions[token]

    return api_response(True)


# ============ 用户 API ============

@app.route('/api/users/me', methods=['GET'])
@require_auth
def get_current_user(user, session):
    """获取当前用户信息"""
    try:
        return api_response(True, data={
            'id': user.user_id,
            'username': user.username,
            'name': user.name,
            'age': user.age,
            'gender': user.gender,
            'memory_group': user.memory_group,
            'user_type': user.user_type,
            'settings': user.settings or {},
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'experiment_phase': user.experiment_phase
        })
    finally:
        session.close()


@app.route('/api/users/me/settings', methods=['POST'])
@require_auth
def update_user_settings(user, session):
    """更新用户设置"""
    data = request.get_json()
    settings = data.get('settings', {})

    db = DBManager(session)
    try:
        db.update_user_settings(user.user_id, settings)
        return api_response(True)
    finally:
        session.close()


# ============ 任务 API ============

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取任务列表"""
    return api_response(True, data=list(TASKS_DATA.values()))


@app.route('/api/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    task = TASKS_DATA.get(task_id)
    if task:
        return api_response(True, data=task)
    return api_response(False, message='任务不存在')


@app.route('/api/users/me/tasks/current', methods=['GET'])
@require_auth
def get_current_task(user, session):
    """获取当前用户的下一个任务"""
    try:
        if user.user_type == 'admin':
            return api_response(True, data=None)

        db = DBManager(session)
        tasks = db.get_user_tasks(user.user_id)
        completed = {t.task_id for t in tasks if t.submitted}

        for task_id in sorted(TASKS_DATA.keys()):
            if task_id not in completed:
                return api_response(True, data=TASKS_DATA[task_id])

        return api_response(True, data=None)
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/start', methods=['POST'])
@require_auth
def start_task_timer(user, session, task_id):
    """启动任务计时器"""
    try:
        db = DBManager(session)
        timer_service = TimerService(db)

        state = timer_service.start_timer(user.user_id, task_id)

        return api_response(True, data={
            'started_at': state.started_at.isoformat() if state.started_at else None,
            'total_duration': state.total_duration,
            'elapsed_time': state.elapsed_time,
            'remaining_time': state.remaining_time,
            'is_expired': state.is_expired
        })
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/timer', methods=['GET'])
@require_auth
def get_task_timer(user, session, task_id):
    """获取任务计时器状态"""
    try:
        db = DBManager(session)
        timer_service = TimerService(db)

        state = timer_service.get_timer_state(user.user_id, task_id)

        return api_response(True, data={
            'started_at': state.started_at.isoformat() if state.started_at else None,
            'total_duration': state.total_duration,
            'elapsed_time': state.elapsed_time,
            'remaining_time': state.remaining_time,
            'is_expired': state.is_expired
        })
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/timer', methods=['POST'])
@require_auth
def update_task_timer(user, session, task_id):
    """更新任务计时器"""
    data = request.get_json()
    elapsed_time = data.get('elapsed_time')

    if elapsed_time is None:
        return api_response(False, message='缺少 elapsed_time 参数')

    try:
        db = DBManager(session)
        timer_service = TimerService(db)

        state = timer_service.update_elapsed_time(user.user_id, task_id, elapsed_time)

        return api_response(True, data={
            'elapsed_time': state.elapsed_time,
            'remaining_time': state.remaining_time,
            'is_expired': state.is_expired
        })
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/submit', methods=['POST'])
@require_auth
def submit_task(user, session, task_id):
    """提交任务"""
    data = request.get_json()
    questionnaire_data = data.get('questionnaire_data', {})

    try:
        db = DBManager(session)
        db.submit_task(user.user_id, task_id, questionnaire_data)

        # 记录日志
        db.log_event(user.user_id, 'task_submit', task_id=task_id)

        # 【新增】触发记忆固化（He et al. 2024）
        # 在 Session 结束后，将短期记忆转化为长期记忆
        try:
            consolidation_service = ConsolidationService(db, llm_manager)
            consolidation_stats = consolidation_service.consolidate_after_session(
                user.user_id,
                task_id,
                user.memory_group
            )

            # 记录固化统计
            print(f"[Consolidation] 固化完成: {consolidation_stats}")
            db.log_event(
                user.user_id,
                'memory_consolidation',
                task_id=task_id,
                event_data=consolidation_stats
            )

        except Exception as e:
            # 固化失败不影响任务提交
            print(f"[Consolidation] 固化失败（不影响任务提交）: {e}")
            import traceback
            traceback.print_exc()

        return api_response(True)
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/document', methods=['GET'])
@require_auth
def get_task_document(user, session, task_id):
    """获取任务文档"""
    try:
        db = DBManager(session)
        task = db.get_or_create_user_task(user.user_id, task_id)

        return api_response(True, data={
            'title': task.document_title or '',
            'content': task.document_content or '',
            'submitted': task.document_submitted,
            'timestamp': task.document_timestamp.isoformat() if task.document_timestamp else None
        })
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/document', methods=['POST'])
@require_auth
def save_task_document(user, session, task_id):
    """保存任务文档"""
    data = request.get_json()

    try:
        db = DBManager(session)
        db.save_task_document(
            user.user_id,
            task_id,
            title=data.get('title', ''),
            content=data.get('content', '')
        )
        return api_response(True)
    finally:
        session.close()


@app.route('/api/users/me/tasks/history', methods=['GET'])
@require_auth
def get_task_history(user, session):
    """获取任务历史"""
    try:
        db = DBManager(session)
        tasks = db.get_user_tasks(user.user_id)

        history = []
        for task in tasks:
            task_info = TASKS_DATA.get(task.task_id)
            if task_info:
                history.append({
                    'taskId': task.task_id,
                    'title': task_info['title'],
                    'description': task_info['description'],
                    'document': {
                        'title': task.document_title or '',
                        'content': task.document_content or '',
                        'submitted': task.document_submitted
                    },
                    'submitted': task.submitted,
                    'submitted_at': task.submitted_at.isoformat() if task.submitted_at else None
                })

        return api_response(True, data=sorted(history, key=lambda x: x['taskId']))
    finally:
        session.close()


# ============ 聊天 API ============

@app.route('/api/users/me/tasks/<int:task_id>/chats', methods=['GET'])
@require_auth
def get_task_chats(user, session, task_id):
    """获取任务聊天记录"""
    try:
        db = DBManager(session)
        messages = db.get_task_messages(user.user_id, task_id)

        return api_response(True, data=[{
            'message_id': msg.message_id,
            'content': msg.content,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
        } for msg in messages])
    finally:
        session.close()


@app.route('/api/users/me/tasks/<int:task_id>/chats', methods=['POST'])
@require_auth
def save_chat_message(user, session, task_id):
    """保存聊天消息"""
    data = request.get_json()

    try:
        db = DBManager(session)
        db.add_message(
            user_id=user.user_id,
            task_id=task_id,
            content=data['content'],
            is_user=data['isUser']
        )
        return api_response(True)
    finally:
        session.close()


@app.route('/api/users/me/chats/history', methods=['GET'])
@require_auth
def get_chat_history(user, session):
    """获取聊天历史概览"""
    try:
        db = DBManager(session)
        tasks = db.get_user_tasks(user.user_id)

        history = []
        for task in tasks:
            messages = db.get_task_messages(user.user_id, task.task_id)
            if messages:
                task_info = TASKS_DATA.get(task.task_id)
                history.append({
                    'taskId': task.task_id,
                    'title': task_info['title'] if task_info else f'任务{task.task_id}',
                    'messageCount': len(messages),
                    'lastMessage': messages[-1].timestamp.isoformat() if messages else None
                })

        return api_response(True, data=sorted(history, key=lambda x: x['taskId']))
    finally:
        session.close()


# ============ AI 对话 API（核心） ============

@app.route('/api/ai/response', methods=['POST'])
@require_auth
def get_ai_response(user, session):
    """获取 AI 回复（非流式）"""
    if user.user_type == 'admin':
        return api_response(False, message='管理员不能与AI交互', status=403)

    data = request.get_json()
    task_id = data.get('taskId')
    user_message = data.get('userMessage')
    response_style = data.get('responseStyle', 'high')

    if not all([task_id, user_message]):
        return api_response(False, message='缺少必要参数')

    try:
        db = DBManager(session)
        timer_service = TimerService(db)
        memory_engine = MemoryEngine(db, llm_manager)

        # 1. 处理计时器，检查是否可以继续
        timer_state, can_continue = timer_service.process_interaction_timer(
            user.user_id, task_id
        )

        if not can_continue:
            return api_response(False, message='对话时间已结束', status=403)

        # 2. 保存用户消息
        db.add_message(user.user_id, task_id, user_message, is_user=True)

        # 3. 获取记忆上下文
        memory_engine.set_current_query(user_message)
        memory_text = memory_engine.get_memory_context(
            user.user_id,
            user.memory_group,
            task_id
        )

        # 4. 构建系统提示词
        system_prompt = build_system_prompt(task_id, user.memory_group, memory_text)

        # 5. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加当前任务的对话历史（最近10条）
        task_messages = db.get_task_messages(user.user_id, task_id)
        for msg in task_messages[-10:]:
            role = "user" if msg.is_user else "assistant"
            messages.append({"role": role, "content": msg.content})

        # 添加当前消息
        messages.append({"role": "user", "content": user_message})

        # 6. 调用 LLM
        temperature = 0.9 if response_style == 'high' else 0.6
        max_tokens = 2000 if response_style == 'high' else 1000

        ai_response = llm_manager.generate_response(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # 7. 保存 AI 回复
        db.add_message(user.user_id, task_id, ai_response, is_user=False)

        # 8. 记录日志
        db.log_event(user.user_id, 'message_sent', task_id=task_id)

        return api_response(True, data={'message': ai_response})

    except Exception as e:
        print(f"[AI响应错误] {e}")
        import traceback
        traceback.print_exc()
        return api_response(False, message=f'AI响应生成失败: {str(e)}', status=500)
    finally:
        session.close()


@app.route('/api/ai/response/stream', methods=['POST'])
@require_auth
def get_ai_response_stream(user, session):
    """获取 AI 流式回复"""
    if user.user_type == 'admin':
        session.close()
        return api_response(False, message='管理员不能与AI交互', status=403)

    data = request.get_json()
    task_id = data.get('taskId')
    user_message = data.get('userMessage')
    response_style = data.get('responseStyle', 'high')

    if not all([task_id, user_message]):
        session.close()
        return api_response(False, message='缺少必要参数')

    # 预先检查计时器
    db = DBManager(session)
    timer_service = TimerService(db)

    timer_state, can_continue = timer_service.process_interaction_timer(
        user.user_id, task_id
    )

    if not can_continue:
        session.close()
        return api_response(False, message='对话时间已结束', status=403)

    # 保存用户消息
    db.add_message(user.user_id, task_id, user_message, is_user=True)

    # 获取记忆上下文
    memory_engine = MemoryEngine(db, llm_manager)
    memory_engine.set_current_query(user_message)
    memory_text = memory_engine.get_memory_context(
        user.user_id,
        user.memory_group,
        task_id
    )

    # 构建提示词
    system_prompt = build_system_prompt(task_id, user.memory_group, memory_text)

    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    task_messages = db.get_task_messages(user.user_id, task_id)
    for msg in task_messages[-10:]:
        role = "user" if msg.is_user else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    temperature = 0.9 if response_style == 'high' else 0.6
    max_tokens = 2000 if response_style == 'high' else 1000

    # 流式生成
    def generate():
        full_response = ""
        try:
            for chunk in llm_manager.generate_response_stream(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            ):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

            # 保存完整回复（需要新的 session）
            _, new_session = get_db()
            new_db = DBManager(new_session)
            new_db.add_message(user.user_id, task_id, full_response, is_user=False)
            new_db.log_event(user.user_id, 'message_sent', task_id=task_id)
            new_session.close()

        except Exception as e:
            print(f"[流式响应错误] {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    session.close()
    return Response(stream_with_context(generate()), content_type='text/event-stream')


# ============ 问卷 API ============

@app.route('/api/users/me/tasks/<int:task_id>/questionnaire', methods=['POST'])
@require_auth
def save_questionnaire(user, session, task_id):
    """保存问卷"""
    data = request.get_json()
    responses = data.get('responses', {})

    try:
        db = DBManager(session)
        task = db.get_or_create_user_task(user.user_id, task_id)
        task.questionnaire_data = responses
        session.commit()
        return api_response(True)
    finally:
        session.close()


# ============ 实验进度 API ============

@app.route('/api/experiment/progress', methods=['GET'])
@require_auth
def get_experiment_progress(user, session):
    """获取实验进度"""
    try:
        db = DBManager(session)
        tasks = db.get_user_tasks(user.user_id)
        completed = sum(1 for t in tasks if t.submitted)

        return api_response(True, data={
            'completed_tasks': completed,
            'total_tasks': 4,
            'progress_percentage': (completed / 4) * 100,
            'current_phase': user.experiment_phase
        })
    finally:
        session.close()


# ============ 管理员 API ============

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_get_users(user, session):
    """获取所有用户"""
    try:
        db = DBManager(session)
        users = db.get_all_users(user_type='normal')

        result = []
        for u in users:
            stats = db.get_user_stats(u.user_id)
            result.append({
                'id': u.user_id,
                'username': u.username,
                'name': u.name,
                'age': u.age,
                'gender': u.gender,
                'memory_group': u.memory_group,
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'experiment_phase': u.experiment_phase,
                'completed_tasks': stats.get('completed_tasks', 0),
                'total_tasks': 4
            })

        return api_response(True, data=result)
    finally:
        session.close()


@app.route('/api/admin/users/<user_id>', methods=['GET'])
@require_admin
def admin_get_user(user, session, user_id):
    """获取用户详情"""
    try:
        db = DBManager(session)
        target = db.get_user(user_id)

        if not target:
            return api_response(False, message='用户不存在')

        if target.user_type != 'normal':
            return api_response(False, message='只能查看普通用户')

        stats = db.get_user_stats(user_id)
        tasks = db.get_user_tasks(user_id)

        return api_response(True, data={
            'user_id': target.user_id,
            'username': target.username,
            'name': target.name,
            'age': target.age,
            'gender': target.gender,
            'memory_group': target.memory_group,
            'experiment_phase': target.experiment_phase,
            'created_at': target.created_at.isoformat() if target.created_at else None,
            'stats': stats,
            'tasks': [{
                'task_id': t.task_id,
                'submitted': t.submitted,
                'timer_elapsed': t.timer_elapsed_time
            } for t in tasks]
        })
    finally:
        session.close()


# ============ 系统提示词构建 ============

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

    # 记忆模式指令
    memory_instructions = {
        "sensory_memory": (
            "\n\n【记忆模式：感觉记忆】你没有任何关于用户的记忆，每次对话都是全新的开始。"
            "你无法记住任何之前的对话内容，请不要假装记得。"
            "如果用户提到'之前说过'，请诚实地表示你不记得。"
        ),
        "working_memory": (
            "\n\n【记忆模式：工作记忆】你只能记住最近几轮的对话内容（约7轮）。"
            "更早的对话内容已经从你的记忆中消失。"
            "请基于这些有限的近期记忆与用户交流，如果用户提到更早的事情，你可能不记得了。"
        ),
        "gist_memory": (
            "\n\n【记忆模式：要义记忆】你记得之前对话的大致内容和要点，但不一定记得具体的措辞。"
            "你了解用户的基本情况和主要话题，但具体细节可能模糊。"
            "这就像人类的自然记忆一样——记得'聊过什么'但不一定记得'原话怎么说'。"
        ),
        "hybrid_memory": (
            "\n\n【记忆模式：混合记忆】你拥有两种记忆能力："
            "(1) 清晰记得最近的对话内容；"
            "(2) 能够回想起与当前话题相关的历史细节。"
            "当用户提到某个话题时，相关的过往记忆会被唤醒。"
            "请充分利用这些记忆，展现对用户的深度了解。"
        )
    }

    memory_instruction = memory_instructions.get(memory_group, "")

    # 记忆上下文
    memory_section = ""
    if memory_text:
        memory_section = f"\n\n=== 历史记忆 ===\n{memory_text}\n=== 记忆结束 ==="

    return base_prompt + memory_instruction + memory_section


# ============ 错误处理 ============

@app.errorhandler(404)
def not_found(error):
    return api_response(False, message='接口不存在', status=404)


@app.errorhandler(500)
def internal_error(error):
    return api_response(False, message='服务器内部错误', status=500)


@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理"""
    print(f"[全局异常] {e}")
    import traceback
    traceback.print_exc()
    return api_response(False, message=f'服务器错误: {str(e)}', status=500)


# ============ 启动入口 ============

if __name__ == '__main__':
    print("=" * 50)
    print("AI 记忆能力实验平台 (重构版)")
    print("=" * 50)
    print(f"数据库: {DB_PATH}")
    print(f"LLM: {experiment_config['model_provider']}")
    print("访问地址: http://localhost:8000")
    print("调试接口: http://localhost:8000/api/debug")
    print("=" * 50)
    app.run(debug=True, port=8000, host='0.0.0.0')
