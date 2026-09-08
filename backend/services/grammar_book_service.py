"""Read-only access to original page images for published database units."""

from pathlib import Path
from typing import Optional

from sqlalchemy import or_

from backend.models.grammar import GrammarUnit
from config.config import Config


def page_path(page_number: int) -> Optional[Path]:
    """Return a rendered source page only when a published unit references it."""
    referenced = GrammarUnit.query.filter(
        GrammarUnit.status == "published",
        or_(
            GrammarUnit.body_source_page == page_number,
            GrammarUnit.exercise_source_page == page_number,
        ),
    ).first()
    if referenced is None:
        return None

    path = Path(Config.GRAMMAR_BOOK_PAGES_DIR) / f"page-{page_number:03d}.png"
    return path if path.is_file() else None
