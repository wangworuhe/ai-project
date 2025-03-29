from flask import Blueprint
from backend.controllers.tts_controller import synthesize_tts

tts_bp = Blueprint("tts", __name__)

# 将请求转发给控制层
tts_bp.route("/synthesize", methods=["POST"])(synthesize_tts)
    