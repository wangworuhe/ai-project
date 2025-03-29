from flask import Blueprint
from backend.controllers.assessment_controller import upload_audio, assess_pronunciation

assessment_bp = Blueprint("assessment", __name__)

assessment_bp.route("/upload", methods=["POST"])(upload_audio)
assessment_bp.route("/assess", methods=["POST"])(assess_pronunciation)
