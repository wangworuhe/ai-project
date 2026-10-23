"""Personal account authentication with revocable, fixed 60-day sessions."""
from collections import deque
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3
from threading import Lock
from time import time

from flask import jsonify, request
from werkzeug.security import check_password_hash

LIFETIME = 60 * 24 * 60 * 60
COOKIE = "ai_project_session"


def install_auth(app, *, clock=time):
    enabled = app.config.get("AUTH_ENABLED", False)
    username = app.config.get("AUTH_USERNAME", "")
    password_hash = app.config.get("AUTH_PASSWORD_HASH", "")
    if enabled and (not username or not password_hash):
        raise RuntimeError("Authentication requires a username and password hash")
    database = Path(app.config.get("AUTH_DATABASE_PATH", "storage/database/auth.db"))
    fingerprint = hashlib.sha256(password_hash.encode()).hexdigest()
    failures = deque()
    lock = Lock()
    if enabled:
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(database)) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, credential TEXT NOT NULL)")
        database.chmod(0o600)

    def connection():
        return sqlite3.connect(str(database), timeout=10)

    def token_digest():
        return hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()

    def current_session():
        with connection() as conn:
            return conn.execute("SELECT csrf, expires FROM sessions WHERE token=? AND expires>? AND credential=?",
                                (token_digest(), clock(), fingerprint)).fetchone()

    def error(message, status):
        return jsonify(message=message), status

    @app.before_request
    def authenticate():
        if not enabled or not request.path.startswith("/api/"):
            return None
        origin = request.headers.get("Origin")
        if (origin and origin not in app.config["PUBLIC_ALLOWED_ORIGINS"]) or request.headers.get("Sec-Fetch-Site") == "cross-site":
            return error("不允许跨站请求。", 403)
        if request.path in {"/api/health", "/api/auth/session", "/api/auth/login"}:
            return None
        active = current_session()
        if not active:
            return error("请先登录。", 401)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), active[0]):
            return error("登录验证已失效，请刷新页面重试。", 403)
        return None

    @app.after_request
    def no_cache(response):
        if enabled and request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/auth/session")
    def auth_session():
        if not enabled:
            return jsonify(enabled=False, authenticated=True)
        active = current_session()
        if not active:
            return jsonify(enabled=True, authenticated=False), 401
        return jsonify(enabled=True, authenticated=True, username=username, csrf_token=active[0], expires_at=active[1])

    @app.post("/api/auth/login")
    def login():
        if not enabled:
            return error("当前环境未启用登录。", 400)
        # JSON plus a custom header prevents cross-origin form/login CSRF.
        if not request.is_json or request.headers.get("X-Requested-With") != "ai-project":
            return error("请通过登录页面登录。", 403)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return error("登录信息格式错误。", 400)
        supplied_name, password = data.get("username", ""), data.get("password", "")
        if not isinstance(supplied_name, str) or not isinstance(password, str) or len(password) > 1024 or len(supplied_name) > 128:
            return error("账号或密码错误。", 401)
        with lock:
            now = clock()
            while failures and failures[0] <= now - 900:
                failures.popleft()
            if len(failures) >= 10:
                response = jsonify(message="登录尝试过多，请在 15 分钟后重试。")
                response.status_code = 429
                response.headers["Retry-After"] = "900"
                return response
            # Reserve the attempt before password hashing, including concurrent calls.
            failures.append(now)
        valid_password = check_password_hash(password_hash, password)
        if not valid_password or not hmac.compare_digest(supplied_name.encode(), username.encode()):
            return error("账号或密码错误。", 401)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = clock() + LIFETIME
        with connection() as conn:
            conn.execute("DELETE FROM sessions WHERE expires<=? OR token=?", (clock(), token_digest()))
            conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), csrf, expires, fingerprint))
        response = jsonify(authenticated=True, username=username, csrf_token=csrf, expires_at=expires)
        response.set_cookie(COOKIE, token, max_age=LIFETIME, secure=app.config.get("AUTH_COOKIE_SECURE", True), httponly=True, samesite="Lax", path="/")
        return response

    @app.post("/api/auth/logout")
    def logout():
        if enabled:
            with connection() as conn:
                conn.execute("DELETE FROM sessions WHERE token=?", (token_digest(),))
        response = jsonify(authenticated=False)
        response.delete_cookie(COOKIE, path="/", secure=app.config.get("AUTH_COOKIE_SECURE", True), httponly=True, samesite="Lax")
        return response
