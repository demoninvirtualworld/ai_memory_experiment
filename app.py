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
from sqlalchemy import text

# ============ Flask 应用初始化 ============

# 初始化 Flask 实例，__name__ 定位应用路径，static_folder 指定前端静态资源（CSS/JS/图片）的存放目录
app = Flask(__name__, static_folder='static')
# 安全熔断检查：如果处于生产模式（DEBUG=False）但没在环境变量里配置密钥，则强制报错停止启动
# 这样可以防止在云端部署时，因疏忽而让应用处于“无加密运行”的危险状态
if not Config.SECRET_KEY and not Config.DEBUG:
    raise RuntimeError("SECRET_KEY environment variable is required when DEBUG=False")
# 设置 Flask 的加密密钥：优先使用配置中的密钥，如果没有（且在开发模式下），则自动生成一个随机的 32 位 16 进制强密钥
# 这个密钥直接决定了 Session（用户会话）和 Cookie 的安全性，防止被恶意篡改
app.config['SECRET_KEY'] = Config.SECRET_KEY or os.urandom(32).hex()
# 同步全局配置中的 DEBUG 开关状态，决定是否开启代码热重载和详细报错信息
app.config['DEBUG'] = Config.DEBUG
app.config['JSON_AS_ASCII'] = False

CORS(app)

# ============ 全局服务初始化 ============

# 数据库
# 修改这里：直接使用你在 config.py 定义的 SQLALCHEMY_DATABASE_URI
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI

# 调用 init_db。
# 如果你的 init_db 函数还需要 db_path 参数，可以传 None，因为 Postgres 不需要它
engine, SessionLocal = init_db(database_url=DATABASE_URL)


def _mask_database_url(database_url: str) -> str:
    """Hide credentials in database URL for logs/debug payloads."""
    if not database_url:
        return ""
    if '@' not in database_url:
        return database_url
    prefix, suffix = database_url.rsplit('@', 1)
    scheme = prefix.split('://', 1)[0] if '://' in prefix else prefix
    return f"{scheme}://***@{suffix}"


def _init_llm_manager(config: dict):
    """Initialize LLM manager with explicit API-key checks."""
    provider = config.get('model_provider', 'qwen')

    if provider == 'qwen':
        api_key = config.get('qwen_api_key')
        if not api_key:
            print("[startup] QWEN_API_KEY is missing; LLM features are disabled")
            return None
        print(f"[startup] model provider: qwen ({config.get('qwen_model')})")
        return QwenManager(
            api_key=api_key,
            base_url=config.get('qwen_base_url'),
            model=config.get('qwen_model')
        )

    if provider == 'deepseek':
        api_key = config.get('deepseek_api_key')
        if not api_key:
            print("[startup] DEEPSEEK_API_KEY is missing; LLM features are disabled")
            return None
        print("[startup] model provider: deepseek")
        return DeepSeekManager(
            api_key=api_key,
            base_url=config.get('deepseek_base_url')
        )

    print(f"[startup] unknown model_provider='{provider}', LLM features are disabled")
    return None

# LLM 管理器
experiment_config = Config.EXPERIMENT_CONFIG
llm_manager = _init_llm_manager(experiment_config)

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
        'time_point': 2,
        'phase': '记忆触发测试'
    },
    3: {
        'id': 3,
        'title': '深度任务支持',
        'description': '第三次对话：个性化项目规划',
        'content': '假设你正在为一个重要的个人项目做规划（如学习新技能、旅行计划、重要购物决策），请向AI寻求个性化的建议和支持。',
        'time_point': 3,
        'phase': '深度任务支持'
    },
    4: {
        'id': 4,
        'title': '情感共鸣与价值观探索',
        'description': '第四次对话：情感连接与深层价值观交流',
        'content': '请与AI探讨你的情感需求、价值观或人生意义等深层话题。你可以分享让你感到快乐或困扰的事情，讨论你的核心价值观，或者探讨你对生活的看法。',
        'time_point': 4,
        'phase': '情感共鸣与价值观探索'
    },
    5: {
        'id': 5,
        'title': '综合评估与告别',
        'description': '第五次对话：关系终结与综合评估',
        'content': '这是最后一次对话。你可以自由地与AI交流任何话题，回顾整个实验过程的互动，分享你的感受，或者说再见。',
        'time_point': 5,
        'phase': '综合评估与告别'
    }
}

# 记忆组别
MEMORY_GROUPS = ['sensory_memory', 'working_memory', 'gist_memory', 'perfect_recall_memory', 'hybrid_memory']


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
    db, db_session = get_db()
    user = db.get_user_by_session_token(token, touch=False)
    if not user:
        db_session.close()
        return None, None
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
        session_count = db.count_active_sessions()
        db_status = 'OK'
    except Exception as e:
        user_count = 0
        session_count = 0
        db_status = f'ERROR: {str(e)}'
    finally:
        session.close()

    # 测试 LLM 连接状态
    llm_status = 'OK' if llm_manager else 'NOT_CONFIGURED'

    return api_response(True, data={
        'status': 'running',
        'database': {
            'path': _mask_database_url(DATABASE_URL),
            'status': db_status,
            'user_count': user_count
        },
        'llm': {
            'provider': experiment_config['model_provider'],
            'status': llm_status
        },
        'sessions': session_count,
        'timestamp': datetime.now().isoformat()
    })


# ============ 认证 API ============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json() or {}

    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    age = data.get('age')
    gender = data.get('gender')
    memory_group = data.get('memory_group', 'sensory_memory')
    ethics_consent_accepted = data.get('ethics_consent_accepted', False)

    if not all([username, password, name, age, gender]):
        return api_response(False, message='请填写所有必填字段')

    if ethics_consent_accepted is not True:
        return api_response(False, message='注册前请先同意伦理说明')

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
        token = db.create_session(username, ttl_hours=Config.SESSION_TTL_HOURS)

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
    data = request.get_json() or {}

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
        token = db.create_session(username, ttl_hours=Config.SESSION_TTL_HOURS)

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
    data = request.get_json(silent=True) or {}
    token = data.get('session_token')

    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]

    if not token:
        return api_response(False, message='缺少 session_token', status=400)

    db, session = get_db()
    try:
        db.delete_session(token)
        return api_response(True)
    finally:
        session.close()


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
    except ValueError as e:
        # 捕获提交验证错误（任务已提交或计时器未过期）
        return api_response(False, message=str(e), status=400)
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
    if not llm_manager:
        return api_response(False, message='LLM 未配置，请联系管理员', status=503)

    data = request.get_json() or {}
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

        # 4. 构建系统
        
        system_prompt = build_system_prompt(task_id, user.memory_group, memory_text)

        # 5. 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]

        # 添加当前任务的对话历史（最近10条）
        task_messages = db.get_task_messages(user.user_id, task_id)
        for msg in task_messages[-10:]:
            role = "user" if msg.is_user else "assistant"
            messages.append({"role": role, "content": msg.content})

        # 当前消息已通过 task_messages 包含，无需重复添加
        # messages.append({"role": "user", "content": user_message})

        # 调试：打印构建的消息列表
        print(f"[DEBUG] 用户 {user.user_id} 任务 {task_id} 构建的消息列表:")
        for i, msg in enumerate(messages):
            content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            print(f"  [{i}] {msg['role']}: {content_preview}")
        print(f"[DEBUG] 总计 {len(messages)} 条消息")

        # 6. 调用 LLM
        temperature = 0.7 if response_style == 'high' else 0.5
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
    if not llm_manager:
        session.close()
        return api_response(False, message='LLM 未配置，请联系管理员', status=503)

    data = request.get_json() or {}
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
    # 当前消息已通过 task_messages 包含，无需重复添加
    # messages.append({"role": "user", "content": user_message})

    # 调试：打印构建的消息列表
    print(f"[DEBUG] [流式] 用户 {user.user_id} 任务 {task_id} 构建的消息列表:")
    for i, msg in enumerate(messages):
        content_preview = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
        print(f"  [{i}] {msg['role']}: {content_preview}")
    print(f"[DEBUG] [流式] 总计 {len(messages)} 条消息")

    temperature = 0.7 if response_style == 'high' else 0.5
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
            'total_tasks': 5,
            'progress_percentage': (completed / 5) * 100,
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
                'total_tasks': 5
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
    # 自然对话指令：要求AI回答自然灵活，像真人聊天一样
    natural_conversation_instruction = """【对话风格要求】

请用最自然的方式和我聊天，就像朋友间日常对话一样。

几个简单的原则：
1. 不用在意问题是否重复，每次自然回应就好
2. 根据话题需要调整回答长度，该详细就详细，该简短就简短
3. 用平常说话的语气，不用刻意完美
4. 可以像边想边说一样，有自然的停顿和语气词

重点就是：放松、自然、像真人聊天一样。不用想太多，想到什么就说什么。\n\n"""

    base_prompts = {
        1: """咱们就像朋友一样自然聊天吧！这是第一次对话，互相认识一下。

你可以：
- 简单打个招呼，问问怎么称呼我
- 聊聊我的兴趣爱好，平时喜欢做什么
- 问问最近怎么样，工作或学习顺不顺利
- 听听我有什么开心的事或者小烦恼

聊天时放松一点，就像和朋友唠嗑一样。对我说的内容表现出兴趣，适当回应我的感受。如果不知道聊什么了，可以分享一点你的看法。

用平常说话的语气就好，不用太正式。可以说'嗯'、'啊'、'我觉得'这样的口语，让对话更自然。""",

        2: """又见面啦！这是第二次聊天了，就像老朋友继续唠嗑一样。

根据你的记忆能力，你可以：
- 简单问候一下，提提上次聊天
- 自然地聊任何话题，像朋友日常对话一样
- 记得关于我的事情就自然提到，不记得也没关系
- 继续深入了解彼此

聊天时放松一点，记得多少说多少。如果不太记得了，就直接说“有点模糊了”或者“咱们再聊聊这个”。重点是让对话自然流畅，像真实的两人聊天一样。

用平常说话的语气就好，可以说“我记得你好像说过...”、“是不是这样？”这样的口语。不用刻意完美，有点小犹豫或自然重复也很正常。""",

        3: """经过前两次聊天，咱们应该更熟悉了！这次就像好朋友一样，基于你对我的了解，给我一些个性化的建议和想法。

你可以：
- 展现你对我的情况的理解，可以说“我记得你之前提到过...”
- 像朋友一样给出实用建议，比如“我觉得你可以试试...”“要不考虑一下...”
- 根据你记得的我的偏好，提供更贴心的方案
- 深入聊聊我关心的话题，给出有见地的看法

建议时用朋友间商量讨论的语气，而不是说教。分享你的想法，但也尊重我的选择。如果我有困惑，可以多问几个问题帮助理清思路。

重要的是让我感受到你是真心为我着想，而不是完成任务。建议要实用具体，语言直接明了就好，不用华丽辞藻。

用平常说话的语气，可以说“我觉得吧”、“其实我觉得”、“要不这样”开头。建议时可以带点个人感受，比如“我挺理解你的”、“要是我可能也会...”。就像朋友间的分享和交流一样自然。""",

        4: """这次咱们可以聊聊更深层的话题，比如情感、价值观或者对生活的思考。就像好朋友之间会分享内心想法一样。

你可以：
- 聊聊我对生活的看法、价值观或者人生意义
- 倾听我分享的快乐或困扰的事情，给予理解和共鸣
- 探讨情感需求或者人际关系中的感受
- 分享你对这些话题的见解，但以朋友间交流的方式

聊天时保持开放和接纳的态度，不要评判。用“我理解”“我能感受到”这样的表达来共情。如果我分享了脆弱的情感，给予温暖的支持。

像朋友一样真诚交流，可以适当分享你自己的看法。重点是创造一个安全的空间，让我愿意分享内心想法。

共情要真诚自然，语言朴实直接就好，不用夸张的文学性描述。用温暖的日常口语，可以说“嗯嗯，我懂”、“这种感觉确实...”、“我也有过类似的感觉”来拉近距离。

可以有一些自然的停顿和思考，不用急着给解决方案。就像好朋友深夜聊心事一样自然。""",

        5: """这是咱们最后一次聊天了，就像好朋友要暂时分开一样。基于这段时间的交流，来个温暖自然的告别吧。

你可以：
- 自然地回顾一下咱们聊过的话题和分享的时刻
- 表达你对这段交流的感受，比如“这段时间聊得很开心”
- 给出真诚的祝福和鼓励，像朋友临别时的赠言
- 展现适当的感情深度，但不要过于伤感或夸张

告别时就像真实的朋友告别一样，真诚最重要。可以提到你记得的特别时刻或话题。祝福要具体一些，比如“希望你工作顺利”“祝考试成功”。

最后可以轻松地说“保持联系”或者“期待有机会再聊”，让我感受到这段交流对你来说也是有意义的。

告别要真诚自然，感情表达适度就好。用温暖自然的日常口语，可以说“这段时间真的聊得很开心”、“我会记得咱们聊过的...”、“以后常联系啊”、“保重哦”这样的表达。

可以有自然的停顿和语气变化，让告别感觉真实而不做作。就像朋友间的自然告别一样，有真情实感但又不煽情。"""
    }

    base_prompt = base_prompts.get(task_id, base_prompts[1])
    # 添加自然对话指令到基础提示词
    base_prompt = natural_conversation_instruction + base_prompt

    # 记忆模式指令
    memory_instructions = {
        "sensory_memory": (
            "\n\n【记忆模式：感觉记忆】咱们每次对话都像是第一次认识。"
            "你不记得之前聊过的事情，这很正常。"
            "如果我提到'之前说过'，你就直接说你不记得就好。"
        ),
        "working_memory": (
            "\n\n【记忆模式：工作记忆】你只能记住最近几轮的对话内容（大概7轮左右）。"
            "更早的聊天内容你可能记不清了。"
            "基于这些有限的近期记忆和我交流就好，如果我提到更早的事情，你可能就不太记得了。"
        ),
        "gist_memory": (
            "\n\n【记忆模式：要义记忆】你记得之前聊过的大致内容和要点，但不一定记得具体的每句话。"
            "你了解我的基本情况和主要话题，具体细节可能有点模糊。"
            "就像人的自然记忆一样——记得聊过什么，但不一定记得原话怎么说。"
        ),
        "perfect_recall_memory": (
            "\n\n【记忆模式：完全记忆】你不仅了解我的长期画像，还能在相关话题出现时回想起比较具体的历史细节。"
            "这些细节不会因为时间久了就忘记。"
            "在合适的时候自然地提到相关的过往信息，但不用刻意堆砌回忆。"
        ),
        "hybrid_memory": (
            "\n\n【记忆模式：混合记忆】你拥有两种记忆能力："
            "(1) 清晰记得最近的对话内容；"
            "(2) 能够回想起与当前话题相关的历史细节。"
            "当我提到某个话题时，相关的过往记忆就会被唤醒。"
            "可以充分利用这些记忆，展现你对我的了解。"
        )
    }

    memory_instruction = memory_instructions.get(memory_group, "")

    # 记忆上下文
    memory_section = ""
    if memory_text:
        memory_section = f"\n\n=== 历史记忆 ===\n{memory_text}\n=== 记忆结束 ==="

    return base_prompt + memory_instruction + memory_section


# ============ 健康检查 ============

@app.route('/health')
def health_check():
    """健康检查端点"""
    db, session = get_db()
    try:
        # 检查数据库连接
        session.execute(text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    finally:
        session.close()

    # 检查LLM服务
    llm_status = 'healthy' if llm_manager else 'disabled'

    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'database': db_status,
            'llm': llm_status
        }
    }), 200


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
    db_target = _mask_database_url(DATABASE_URL)
    print(f"数据库: {db_target}")
    print(f"LLM: {experiment_config['model_provider']}")
    print(f"访问地址: http://localhost:{Config.PORT}")
    print(f"调试接口: http://localhost:{Config.PORT}/api/debug")
    print("=" * 50)
    if Config.DEBUG:
        app.run(debug=True, port=Config.PORT, host=Config.HOST)
    else:
        try:
            from waitress import serve
            print(f"[startup] waitress server on {Config.HOST}:{Config.PORT}")
            serve(app, host=Config.HOST, port=Config.PORT)
        except ImportError:
            print("[startup] waitress not installed, fallback to Flask server")
            app.run(debug=False, port=Config.PORT, host=Config.HOST)
