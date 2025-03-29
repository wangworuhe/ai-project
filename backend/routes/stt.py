from flask import Blueprint
from backend.controllers.stt_controller import recognize_speech, recognize_from_file

stt_bp = Blueprint("stt", __name__)

stt_bp.route("/recognize-mic", methods=["GET"])(recognize_speech)
stt_bp.route("/recognize", methods=["POST"])(recognize_from_file)
