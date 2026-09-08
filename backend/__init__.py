from flask import Flask, send_from_directory
from config.config import Config
from config.logging_config import configure_logging
from backend.extensions import db, migrate
from backend.models import init_db
from backend.routes.tts import tts_bp
from backend.routes.google_tts import google_tts_bp
from backend.routes.stt import stt_bp
from backend.routes.assessment import assessment_bp
from backend.routes.translation import translation_bp
from backend.routes.cambridge import cambridge_bp
from backend.routes.grammar import grammar_bp

from flask_cors import CORS

def create_app():
    print("Initializing app...")
    # 配置日志
    configure_logging()

    app = Flask(__name__)
    app.config.from_object('config.config.Config')

    CORS(app)  # 允许所有来源访问

    init_db(app)
    migrate.init_app(app, db)

    # 注册蓝图
    app.register_blueprint(tts_bp, url_prefix="/api/tts")
    app.register_blueprint(google_tts_bp, url_prefix="/api/google-tts")
    app.register_blueprint(stt_bp, url_prefix="/api/stt")
    app.register_blueprint(assessment_bp, url_prefix="/api/assessment")
    app.register_blueprint(translation_bp, url_prefix="/api/translation")
    app.register_blueprint(cambridge_bp)
    app.register_blueprint(grammar_bp, url_prefix="/api/grammar")

    @app.get("/api/health")
    def health_check():
        return {"status": "ok"}

    @app.get("/api/media/<path:filename>")
    def media_file(filename):
        return send_from_directory(app.config["OUTPUT_DIR"], filename)

    return app
