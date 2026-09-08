from flask import Blueprint

from backend.controllers.grammar_controller import (
    get_book_page,
    get_library_media,
    get_library_unit,
    get_library_units,
)


grammar_bp = Blueprint("grammar", __name__)
grammar_bp.get("/book-pages/<int:page_number>")(get_book_page)
grammar_bp.get("/library/units")(get_library_units)
grammar_bp.get("/library/units/<int:unit_number>")(get_library_unit)
grammar_bp.get("/library/media/<int:media_id>")(get_library_media)
