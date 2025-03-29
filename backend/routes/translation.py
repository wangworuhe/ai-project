from flask import Blueprint
from backend.controllers.translation_controller import translate_text

translation_bp = Blueprint("translation", __name__)

translation_bp.route("/translate", methods=["POST"])(translate_text)
