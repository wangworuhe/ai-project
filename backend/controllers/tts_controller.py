from flask import request, jsonify
from backend.services.tts_service import text_to_speech

def synthesize_tts():
    """ 处理 TTS 语音合成请求 """
    try:
        data = request.get_json()
        text = data.get("text")
        voice = data.get("voice", "en-US-JennyNeural")

        if not text:
            return jsonify({"status": "error", "message": "请输入要转换的文本"}), 400

        response = text_to_speech(text, voice)

        if "error" in response:
            return jsonify({"status": "error", "message": response["error"]}), 500

        return jsonify({"status": "success", "data": {"file": response["file"]}})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
# Compare this snippet from ai-project/backend/services/tts_service.py:
# from azure.cognitiveservices.speech import SpeechSynthesizer, SpeechConfig, AudioOutputConfig 