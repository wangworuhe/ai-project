from flask import current_app, jsonify, request

from backend.services.google_tts_service import text_to_google_speech


def synthesize_google_tts():
    """Handle the independent Google Translate TTS endpoint."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "请求内容必须为 JSON"}), 400

    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"status": "error", "message": "请输入要转换的文本"}), 400

    result = text_to_google_speech(
        text=text,
        lang=(data.get("lang") or "en").strip(),
        tld=(data.get("tld") or "com").strip(),
        slow=data.get("slow") is True,
    )
    if "error" in result:
        current_app.logger.warning("Google TTS failed: %s", result["error"])
        return jsonify({"status": "error", "message": result["error"]}), result["status"]

    return jsonify({"status": "success", "data": {"file": result["url"]}})
