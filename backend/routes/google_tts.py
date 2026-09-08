from flask import Blueprint

from backend.controllers.google_tts_controller import synthesize_google_tts


google_tts_bp = Blueprint("google_tts", __name__)
google_tts_bp.route("/synthesize", methods=["POST"])(synthesize_google_tts)
