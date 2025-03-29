# app/routes.py
from flask import request, current_app

def register_routes(app):
    # 记录请求信息
    @app.before_request
    def log_request():
        current_app.logger.info(
            f"Request: {request.method} {request.path} from {request.remote_addr}"
        )

    # 记录响应信息
    @app.after_request
    def log_response(response):
        current_app.logger.info(
            f"Response: {response.status} for {request.method} {request.path}"
        )
        return response

    # 示例路由
    @app.route("/")
    def home():
        current_app.logger.debug("Home route accessed")
        return "坚持!"