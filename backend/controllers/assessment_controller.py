from flask import Blueprint, request, jsonify
from backend.services.assessment_service import evaluate_pronunciation, save_audio_file, evaluate_pronunciation_from_file
from backend.extensions import db
from backend.models import db, Assessment

assessment_bp = Blueprint("assessment", __name__)

@assessment_bp.route("/assessment/upload", methods=["POST"])
def upload_audio():
    """
    处理音频文件上传，并进行语音评估
    """
    if "audio" not in request.files:
        return jsonify({"status": "error", "message": "未找到音频文件"}), 400

    audio_file = request.files["audio"]
    reference_text = request.form.get("reference_text", "")
    assessment_type = request.form.get("assessment_type", "scripted")  # 评估类型

    if not reference_text:
        return jsonify({"status": "error", "message": "缺少评估文本"}), 400

    try:
        # 保存音频文件
        file_path = save_audio_file(audio_file, user_id=1)  # 假设 user_id = 1

        # 进行语音评估
        evaluation_result = evaluate_pronunciation_from_file(file_path, reference_text, assessment_type)
        
        detailed_result = evaluation_result.get("detailed_result", {})
        if not detailed_result:
            return jsonify({"status": "error", "message": "Azure 未返回详细评估信息"}), 500

        # 存入数据库
        # new_assessment = Assessment(
        #     user_id=1,  # TODO: 未来支持用户系统
        #     text=reference_text,
        #     pronunciation_score=evaluation_result["pronunciation_score"],
        #     accuracy_score=evaluation_result["accuracy_score"],
        #     fluency_score=evaluation_result["fluency_score"],
        #     completeness_score=evaluation_result["completeness_score"],
        #     prosody_score=evaluation_result.get("prosody_score", 0.0),
        #     vocabulary_score=evaluation_result.get("vocabulary_score", 0.0),
        #     grammar_score=evaluation_result.get("grammar_score", 0.0),
        #     topic_score=evaluation_result.get("topic_score", 0.0),
        #     audio_path=file_path,
        #     audio_duration=evaluation_result["audio_duration"],
        #     assessment_type=assessment_type,
        #     processed_at=db.func.current_timestamp()
        # )
        new_assessment = Assessment(
            user_id=1,  # TODO: 未来支持用户系统
            text=reference_text,
            # 核心发音评分（强制转换为浮点型，避免None导致数据库异常）
            pronunciation_score=float(evaluation_result.get("pronunciation_score", 0.0)),
            accuracy_score=float(evaluation_result.get("accuracy_score", 0.0)),
            fluency_score=float(evaluation_result.get("fluency_score", 0.0)),
            completeness_score=float(evaluation_result.get("completeness_score", 0.0)),
            prosody_score=float(evaluation_result.get("prosody_score", 0.0)),  # 韵律评分
            
            # 内容评估相关评分（兼容字段不存在或空值）
            vocabulary_score=float(evaluation_result.get("vocabulary_score", 0.0)),
            grammar_score=float(evaluation_result.get("grammar_score", 0.0)),
            topic_score=float(evaluation_result.get("topic_score", 0.0)),
            
            # 其他固定字段
            audio_path=file_path,
            audio_duration=float(evaluation_result.get("audio_duration", 0.0)),  # 防止音频时长解析失败
            assessment_type=assessment_type,
            processed_at=db.func.current_timestamp()
        )
        db.session.add(new_assessment)
        db.session.commit()

        return jsonify({
            "status": "success", 
            "data": evaluation_result, 
            "detailed_result": detailed_result,  # 详细评估信息
            "file_path": file_path
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

def assess_pronunciation():
    """ 处理语音评估请求，并存储评分 """
    try:
        data = request.get_json()
        reference_text = data.get("reference_text")
        if not reference_text:
            return jsonify({"status": "error", "message": "请提供 reference_text"}), 400

        result = evaluate_pronunciation(reference_text)

        # 存储到数据库
        assessment = Assessment(
            user_id=1,  # 默认 user_id = 1（待支持用户系统）
            text=reference_text,
            pronunciation_score=result["pronunciation_score"]
        )
        db.session.add(assessment)
        db.session.commit()

        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
