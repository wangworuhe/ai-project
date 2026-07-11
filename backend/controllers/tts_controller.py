from flask import request, jsonify, current_app
from backend.services.tts_service import text_to_speech
from backend.models.tts_log import SynthesisLog
from backend.extensions import db

def synthesize_tts():
    """处理 TTS 请求，记录日志并返回文件 URL"""
    try:
        data = request.get_json()
        text = data.get("text")
        if not text:
            return jsonify({"status":"error","message":"请输入要转换的文本"}), 400

        # 提取 SSML 参数
        locale = data.get("locale", "en-US")
        voice = data.get("voice", "en-US-JennyNeural")
        style = data.get("style")
        styledegree = data.get("styledegree")
        role = data.get("role")
        rate = data.get("rate")
        pitch = data.get("pitch")
        volume = data.get("volume")

        resp = text_to_speech(
            text, locale, voice, style, styledegree, role, rate, pitch, volume
        )
        if "error" in resp:
            current_app.logger.error(f"TTS Error: {resp['error']}")
            return jsonify({"status":"error","message":resp["error"]}), 500

        # 持久化日志
        log = SynthesisLog(
            text=text,
            locale=locale,
            voice=voice,
            style=style,
            styledegree=styledegree,
            role=role,
            rate=rate,
            pitch=pitch,
            volume=volume,
            file_path=resp["file"]
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({"status":"success","data":{"file":resp["file"]}})

    except Exception as e:
        current_app.logger.exception("synthesize_tts 异常")
        return jsonify({"status":"error","message":str(e)}), 500
