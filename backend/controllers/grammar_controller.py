from io import BytesIO

from flask import current_app, jsonify, request, send_file
from backend.extensions import db
from backend.services.grammar_book_service import page_path
from backend.services.grammar_library_service import (
    get_published_media,
    get_published_unit,
    list_published_units,
)
from backend.services.grammar_draft_service import (
    DraftValidationError,
    get_unit_draft,
    save_unit_draft,
)
from backend.services.grammar_grading_service import (
    SubmissionValidationError,
    get_attempt_session,
    submit_unit_attempt,
)
from backend.services.grammar_mistake_service import MistakeQueryError, list_mistakes


def get_book_page(page_number):
    page = page_path(page_number)
    if not page:
        return jsonify({
            "status": "error",
            "message": "Book page is unavailable. Run scripts/build-grammar-book-assets.py first.",
        }), 404
    return send_file(page, mimetype="image/png", conditional=True, max_age=86400)


def get_library_units():
    return jsonify({"status": "success", "data": list_published_units()})


def get_library_unit(unit_number):
    unit = get_published_unit(unit_number)
    if unit is None:
        return jsonify({
            "status": "error",
            "message": "该 Unit 尚未完成结构化导入",
        }), 404
    return jsonify({"status": "success", "data": unit})


def get_library_media(media_id):
    media = get_published_media(media_id)
    if media is None:
        return jsonify({"status": "error", "message": "未找到书籍图片"}), 404
    response = send_file(
        BytesIO(media.content_blob),
        mimetype=media.mime_type,
        conditional=True,
        etag=media.sha256,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    return response


def get_library_unit_draft(unit_number):
    draft = get_unit_draft(unit_number)
    if draft is None:
        return jsonify({"status": "error", "message": "该 Unit 不存在或尚未发布"}), 404
    return jsonify({"status": "success", "data": draft})


def put_library_unit_draft(unit_number):
    if not request.is_json:
        return jsonify({"status": "error", "message": "请求内容必须为 JSON"}), 400
    try:
        result = save_unit_draft(unit_number, request.get_json(silent=True))
    except DraftValidationError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to save grammar draft for Unit %s", unit_number)
        return jsonify({"status": "error", "message": "服务器保存失败，请稍后重试"}), 500
    if result is None:
        return jsonify({"status": "error", "message": "该 Unit 不存在或尚未发布"}), 404
    return jsonify({"status": "success", "data": result})


def post_library_unit_submission(unit_number):
    if not request.is_json:
        return jsonify({"status": "error", "message": "请求内容必须为 JSON"}), 400
    try:
        result = submit_unit_attempt(unit_number, request.get_json(silent=True))
    except SubmissionValidationError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to grade grammar submission for Unit %s", unit_number
        )
        return jsonify({"status": "error", "message": "提交判题失败，请稍后重试"}), 500
    if result is None:
        return jsonify({"status": "error", "message": "该 Unit 不存在或尚未发布"}), 404
    return jsonify({"status": "success", "data": result}), 201


def get_library_submission(session_id):
    result = get_attempt_session(session_id)
    if result is None:
        return jsonify({"status": "error", "message": "未找到该次提交记录"}), 404
    return jsonify({"status": "success", "data": result})


def get_library_mistakes():
    scope = request.args.get("status", "active")
    raw_unit = request.args.get("unit")
    try:
        unit_number = int(raw_unit) if raw_unit is not None else None
        result = list_mistakes(scope=scope, unit_number=unit_number)
    except (ValueError, MistakeQueryError) as error:
        message = str(error) if isinstance(error, MistakeQueryError) else "unit 必须是正整数"
        return jsonify({"status": "error", "message": message}), 400
    return jsonify({"status": "success", "data": result})
