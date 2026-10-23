"""Single-user request budgets for the authenticated public deployment."""

from collections import deque
from threading import BoundedSemaphore, Lock
from time import monotonic

from flask import g, jsonify, request


def install_public_guard(app, *, clock=monotonic):
    if not app.config.get("PUBLIC_ACCESS_ENABLED"):
        return

    allowed_origins = set(app.config["PUBLIC_ALLOWED_ORIGINS"])
    recent = deque()
    paid = deque()
    lock = Lock()
    capacity = BoundedSemaphore(2)

    def reject(message, status, retry_after=None):
        response = jsonify({"status": "error", "message": message})
        response.status_code = status
        if retry_after is not None:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.before_request
    def guard_request():
        if not request.path.startswith("/api/"):
            return None
        origin = request.headers.get("Origin")
        if (origin and origin not in allowed_origins) or request.headers.get("Sec-Fetch-Site") == "cross-site":
            return reject("Cross-site requests are not allowed.", 403)

        if request.method in {"POST", "PUT", "PATCH"}:
            # Enforce the upload bound before controllers can catch a 413 as a 500.
            request.get_data(cache=True)
            if request.is_json:
                payload = request.get_json(silent=True)
                if isinstance(payload, dict) and any(
                    isinstance(payload.get(key), str) and len(payload[key]) > 10000
                    for key in ("text", "reference_text")
                ):
                    return reject("Text must not exceed 10000 characters.", 413)

        expensive = request.path.startswith((
            "/api/tts/", "/api/google-tts/", "/api/stt/",
            "/api/assessment/", "/api/translation/",
        )) or (
            request.method == "POST"
            and (request.path.endswith("/submissions") or request.path.endswith("/ai-review/retry"))
        )
        now = clock()
        with lock:
            while recent and recent[0] <= now - 60:
                recent.popleft()
            while paid and paid[0] <= now - 3600:
                paid.popleft()
            if len(recent) >= 600:
                return reject("Request limit reached; try again shortly.", 429, 60)
            if expensive and (len(paid) >= 120 or sum(t > now - 60 for t in paid) >= 10):
                return reject("Speech/AI request budget reached; try again later.", 429, 60)
            if expensive and not capacity.acquire(blocking=False):
                return reject("Two speech/AI requests are already running.", 429, 5)
            recent.append(now)
            if expensive:
                paid.append(now)
                g.public_guard_capacity = True
        return None

    @app.teardown_request
    def release_capacity(_error):
        if g.pop("public_guard_capacity", False):
            capacity.release()
