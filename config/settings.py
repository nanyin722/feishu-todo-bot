"""
配置管理
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Settings:
    """应用配置类"""

    def __init__(self):
        # 加载环境变量
        load_dotenv()

        # 飞书应用配置
        self.FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', '')
        self.FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', '')
        self.FEISHU_VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', '')
        self.FEISHU_ENCRYPT_KEY = os.getenv('FEISHU_ENCRYPT_KEY', '')

        # Flask配置
        self.FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
        self.FLASK_PORT = int(os.getenv('FLASK_PORT', 8000))
        self.FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

        # 数据库配置
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', './data/todos.db')

        # 日志配置
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.LOG_FILE = os.getenv('LOG_FILE', './logs/bot.log')

        # 验证配置
        self._validate_config()

    def _validate_config(self):
        """验证配置是否完整"""
        errors = []

        if not self.FEISHU_APP_ID:
            errors.append("FEISHU_APP_ID is not set")

        if not self.FEISHU_APP_SECRET:
            errors.append("FEISHU_APP_SECRET is not set")

        if not self.FEISHU_VERIFICATION_TOKEN:
            errors.append("FEISHU_VERIFICATION_TOKEN is not set")

        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Configuration validated successfully")

    def setup_directories(self):
        """创建必要的目录"""
        # 创建数据库目录
        db_dir = Path(self.DATABASE_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory: {db_dir}")

        # 创建日志目录
        log_dir = Path(self.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Log directory: {log_dir}")

    def setup_logging(self):
        """配置日志系统"""
        # 确保日志目录存在
        log_dir = Path(self.LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'

        # 配置根日志记录器
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format=log_format,
            datefmt=date_format,
            handlers=[
                # 文件处理器
                logging.FileHandler(self.LOG_FILE, encoding='utf-8'),
                # 控制台处理器
                logging.StreamHandler()
            ]
        )

        # 设置第三方库的日志级别
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

        logger.info(f"Logging configured: level={self.LOG_LEVEL}, file={self.LOG_FILE}")

    def get_database_url(self) -> str:
        """获取数据库URL"""
        return self.DATABASE_PATH

    def to_dict(self) -> dict:
        """转换为字典（隐藏敏感信息）"""
        return {
            'FEISHU_APP_ID': self.FEISHU_APP_ID,
            'FEISHU_APP_SECRET': '***' if self.FEISHU_APP_SECRET else '',
            'FEISHU_VERIFICATION_TOKEN': '***' if self.FEISHU_VERIFICATION_TOKEN else '',
            'FEISHU_ENCRYPT_KEY': '***' if self.FEISHU_ENCRYPT_KEY else '',
            'FLASK_HOST': self.FLASK_HOST,
            'FLASK_PORT': self.FLASK_PORT,
            'FLASK_DEBUG': self.FLASK_DEBUG,
            'DATABASE_PATH': self.DATABASE_PATH,
            'LOG_LEVEL': self.LOG_LEVEL,
            'LOG_FILE': self.LOG_FILE,
        }


# 全局配置实例
settings = Settings()
