"""
飞书待办机器人 - Flask应用主入口
"""
import json
import logging
from collections import deque
from flask import Flask, request, jsonify

from config.settings import settings
from database.db import Database
from bot.feishu_client import FeishuClient
from bot.message_handler import MessageHandler
from scheduler.reminder import ReminderService
from scheduler.jobs import create_scheduler

# 配置日志
settings.setup_logging()
settings.setup_directories()

logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 初始化组件
logger.info("Initializing application components...")

# 数据库
database = Database(settings.get_database_url())
logger.info(f"Database initialized: {settings.get_database_url()}")

# 飞书客户端
feishu_client = FeishuClient(
    app_id=settings.FEISHU_APP_ID,
    app_secret=settings.FEISHU_APP_SECRET,
    folder_token=settings.FEISHU_FOLDER_TOKEN
)
logger.info("Feishu client initialized")

# 消息处理器
message_handler = MessageHandler(feishu_client, database)
logger.info("Message handler initialized")

# 提醒服务
reminder_service = ReminderService(feishu_client, database)
logger.info("Reminder service initialized")

# 调度器
scheduler_manager = create_scheduler(reminder_service)
logger.info("Scheduler manager created")

# 已处理的事件ID集合（内存去重，防止飞书 webhook 重试导致重复处理）
_processed_event_ids: deque = deque(maxlen=500)


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'feishu-todo-bot',
        'scheduler_running': scheduler_manager.scheduler.running,
        'jobs': len(scheduler_manager.get_jobs())
    })


@app.route('/webhook/event', methods=['POST'])
def handle_event():
    """
    处理飞书事件回调

    飞书会发送以下类型的请求：
    1. url_verification - URL验证请求
    2. event_callback - 事件回调请求
    """
    try:
        # 获取请求数据
        data = request.get_json()

        if not data:
            logger.warning("Received empty request")
            return jsonify({'error': 'Empty request'}), 400

        logger.info(f"Received event: {json.dumps(data, ensure_ascii=False)}")

        # 处理URL验证请求
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge', '')
            logger.info(f"URL verification request, challenge: {challenge}")
            return jsonify({'challenge': challenge})

        # 验证Token
        token = data.get('header', {}).get('token', '')
        if token != settings.FEISHU_VERIFICATION_TOKEN:
            logger.warning(f"Invalid verification token: {token}")
            return jsonify({'error': 'Invalid token'}), 401

        # 事件去重（防止飞书 webhook 重试导致重复处理）
        event_id = data.get('header', {}).get('event_id', '')
        if event_id:
            if event_id in _processed_event_ids:
                logger.info(f"Duplicate event ignored: {event_id}")
                return jsonify({'msg': 'ok'})
            _processed_event_ids.append(event_id)

        # 处理事件回调
        if data.get('header', {}).get('event_type') == 'im.message.receive_v1':
            event_data = data.get('event', {})

            # 过滤机器人自己的消息
            sender = event_data.get('sender', {})
            sender_type = sender.get('sender_type', '')
            if sender_type == 'app':
                logger.info("Ignoring message from bot itself")
                return jsonify({'msg': 'ok'})

            # 处理消息
            message_handler.handle_message(event_data)

        return jsonify({'msg': 'ok'})

    except Exception as e:
        logger.error(f"Error handling event: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/todos', methods=['GET'])
def get_todos():
    """获取待办列表（管理接口）"""
    try:
        chat_id = request.args.get('chat_id')
        if not chat_id:
            return jsonify({'error': 'chat_id is required'}), 400

        todos = database.get_todos_by_chat(chat_id, include_completed=False)
        return jsonify({
            'count': len(todos),
            'todos': [todo.to_dict() for todo in todos]
        })

    except Exception as e:
        logger.error(f"Error getting todos: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/reminder/trigger/<job_id>', methods=['POST'])
def trigger_reminder(job_id):
    """手动触发提醒任务（测试接口）"""
    try:
        scheduler_manager.trigger_job(job_id)
        return jsonify({'msg': f'Job {job_id} triggered successfully'})

    except Exception as e:
        logger.error(f"Error triggering job: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """获取调度任务列表"""
    try:
        jobs = scheduler_manager.get_jobs()
        jobs_info = []

        for job in jobs:
            jobs_info.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })

        return jsonify({
            'count': len(jobs_info),
            'jobs': jobs_info
        })

    except Exception as e:
        logger.error(f"Error getting jobs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def start_application():
    """启动应用"""
    try:
        logger.info("=" * 60)
        logger.info("Starting Feishu Todo Bot Application")
        logger.info("=" * 60)

        # 打印配置信息
        logger.info("Configuration:")
        for key, value in settings.to_dict().items():
            logger.info(f"  {key}: {value}")

        # 启动调度器
        scheduler_manager.start()
        logger.info("Scheduler started")

        # 启动Flask应用
        logger.info(f"Starting Flask server on {settings.FLASK_HOST}:{settings.FLASK_PORT}")
        app.run(
            host=settings.FLASK_HOST,
            port=settings.FLASK_PORT,
            debug=settings.FLASK_DEBUG
        )

    except Exception as e:
        logger.error(f"Error starting application: {e}", exc_info=True)
        raise
    finally:
        # 停止调度器
        scheduler_manager.stop()
        logger.info("Application stopped")


if __name__ == '__main__':
    start_application()
