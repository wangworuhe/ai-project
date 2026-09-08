from io import BytesIO

from flask import jsonify, send_file
from backend.services.grammar_book_service import page_path
from backend.services.grammar_library_service import (
    get_published_media,
    get_published_unit,
    list_published_units,
)


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
