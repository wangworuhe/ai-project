# config/logging_config.py
import os
import logging
from logging.config import dictConfig

from config.config import Config

def configure_logging():
    """动态配置日志系统（支持环境变量覆盖）"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = Config.LOG_FILE

    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 日志配置字典
    logging_config = {
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'default',
                'level': log_level
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file,
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'formatter': 'default',
                'level': log_level
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console', 'file']
        }
    }

    dictConfig(logging_config)
