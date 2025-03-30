
from flask import Blueprint
from backend.controllers.cambridge_controller import fetch_pronunciation

cambridge_bp = Blueprint('cambridge', __name__, url_prefix='/api/cambridge')
cambridge_bp.route('', methods=['GET'])(fetch_pronunciation)
