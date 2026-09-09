from backend.extensions import db
from sqlalchemy import text
from backend.models.user import User
from backend.models.recording import Recording
from backend.models.assessment import Assessment
from backend.models.tts_log import SynthesisLog
from backend.models.grammar import (
    GrammarAnswerSlot,
    GrammarAnswerKeyEntry,
    GrammarAnswerVariant,
    GrammarAttempt,
    GrammarBook,
    GrammarContentBlock,
    GrammarDraft,
    GrammarDraftAnswer,
    GrammarExercise,
    GrammarMedia,
    GrammarMistake,
    GrammarQuestion,
    GrammarSolution,
    GrammarUnit,
)

def init_db(app):
    """ 初始化数据库 """
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # db.create_all() does not add columns to an existing SQLite table.
        # This small, idempotent migration keeps current local installations compatible.
        def columns(table_name):
            return {
                row[1]
                for row in db.session.execute(
                    text(f"PRAGMA table_info({table_name})")
                )
            }

        if "answer_key_entry_id" not in columns("grammar_solutions"):
            db.session.execute(text(
                "ALTER TABLE grammar_solutions "
                "ADD COLUMN answer_key_entry_id INTEGER "
                "REFERENCES grammar_answer_key_entries(id) ON DELETE SET NULL"
            ))
        if "asset_key" not in columns("grammar_media"):
            db.session.execute(text(
                "ALTER TABLE grammar_media ADD COLUMN asset_key VARCHAR(100)"
            ))
        for table_name in (
            "grammar_exercises", "grammar_questions", "grammar_answer_slots"
        ):
            if "is_active" not in columns(table_name):
                db.session.execute(text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                ))

        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ix_grammar_solutions_answer_key_entry_id "
            "ON grammar_solutions(answer_key_entry_id)"
        ))
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ix_grammar_media_unit_asset_key "
            "ON grammar_media(unit_id, asset_key)"
        ))
        for table_name in (
            "grammar_exercises", "grammar_questions", "grammar_answer_slots"
        ):
            db.session.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{table_name}_is_active "
                f"ON {table_name}(is_active)"
            ))
        db.session.commit()
