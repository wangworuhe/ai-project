from flask import request, jsonify
from backend.services.stt_service import recognize_speech_mic, recognize_speech_file
from backend.extensions import db
from backend.models.recording import Recording
import os

UPLOAD_FOLDER = "./outputs/"  # 录音存储目录

def recognize_speech():
    """ 处理麦克风语音识别请求 """
    try:
        text, filename = recognize_speech_mic(UPLOAD_FOLDER)

        # 存储到数据库
        recording = Recording(user_id=1, filename=filename)  # 默认 user_id = 1（待支持用户系统）
        db.session.add(recording)
        db.session.commit()

        # result = recognize_speech_mic()
        return jsonify({"status": "success", "data": {"text": filename}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def recognize_from_file():
    """ 处理音频文件语音识别请求 """
    try:
        if "audio" not in request.files:
            return jsonify({"status": "error", "message": "请上传音频文件"}), 400

        audio_file = request.files["audio"]
        text, filename = recognize_speech_file(audio_file, UPLOAD_FOLDER)

        # 存储到数据库
        recording = Recording(user_id=1, filename=filename)
        db.session.add(recording)
        db.session.commit()

        # result = recognize_speech_file(audio_file)
        return jsonify({"status": "success", "data": {"text": filename}})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
