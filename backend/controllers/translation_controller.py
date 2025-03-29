from flask import request, jsonify
from googletrans import Translator

translator = Translator()

def translate_text():
    """ 处理翻译请求 """
    try:
        data = request.get_json()
        text = data.get("text", "")
        target_language = data.get("target_language", "zh-CN")

        if not text:
            return jsonify({"status": "error", "message": "请输入文本"}), 400

        result = translator.translate(text, dest=target_language)

        return jsonify({
            "status": "success",
            "data": {
                "original_text": result.origin,
                "translated_text": result.text,
                "source_language": result.src
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
