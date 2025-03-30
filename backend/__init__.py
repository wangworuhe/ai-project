from flask import Flask
from config.config import Config
from config.logging_config import configure_logging
from backend.extensions import db, migrate
from backend.models import init_db
from backend.routes.tts import tts_bp
from backend.routes.stt import stt_bp
from backend.routes.assessment import assessment_bp
from backend.routes.translation import translation_bp
from backend.routes.cambridge import cambridge_bp

from flask_cors import CORS

def create_app():
    print("Initializing app...")
    # 配置日志
    configure_logging()

    app = Flask(__name__)
    app.config.from_object('config.config.Config')
    
    # 移除 Flask 默认的日志处理器（可选）
    # from flask.logging import default_handler
    # app.logger.removeHandler(default_handler)

    CORS(app)  # 允许所有来源访问

    init_db(app)
    migrate.init_app(app, db)

    # 注册蓝图
    app.register_blueprint(tts_bp, url_prefix="/tts")
    app.register_blueprint(stt_bp, url_prefix="/stt")
    app.register_blueprint(assessment_bp, url_prefix="/assessment")
    app.register_blueprint(translation_bp, url_prefix="/translation")
    app.register_blueprint(cambridge_bp)

    return app
