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
        columns = {
            row[1]
            for row in db.session.execute(
                text("PRAGMA table_info(grammar_solutions)")
            )
        }
        if "answer_key_entry_id" not in columns:
            db.session.execute(text(
                "ALTER TABLE grammar_solutions "
                "ADD COLUMN answer_key_entry_id INTEGER "
                "REFERENCES grammar_answer_key_entries(id) ON DELETE SET NULL"
            ))
            db.session.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_grammar_solutions_answer_key_entry_id "
                "ON grammar_solutions(answer_key_entry_id)"
            ))
            db.session.commit()
