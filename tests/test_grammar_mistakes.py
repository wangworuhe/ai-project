import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Flask

from backend.extensions import db
from backend.models.grammar import (
    GrammarAttemptAnswer,
    GrammarAttemptSession,
    GrammarBook,
    GrammarExercise,
    GrammarMistakeEntry,
    GrammarQuestion,
    GrammarUnit,
)
from backend.services.grammar_mistake_service import (
    apply_attempt_answer,
    list_mistakes,
    sync_existing_attempts,
)


class GrammarMistakeBookTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            GRAMMAR_DRAFT_PROFILE="test-profile",
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        book = GrammarBook(
            slug="test-book",
            title="Test Book",
            edition="1",
            source_filename="test.pdf",
            source_sha256="a" * 64,
            total_pages=10,
        )
        unit = GrammarUnit(
            book=book,
            unit_number=1,
            title="Present continuous",
            grammar_point="present-continuous",
            body_source_page=1,
            exercise_source_page=2,
            sort_order=1,
            status="published",
        )
        exercise = GrammarExercise(
            unit=unit,
            exercise_number="1.1",
            instruction="Complete the sentence.",
            exercise_type="fill",
            source_page=2,
            sort_order=1,
        )
        self.question = GrammarQuestion(
            exercise=exercise,
            question_number="2",
            question_type="fill",
            content_json={"prompt": "Why are you crying?"},
            sort_order=1,
            source_page=2,
        )
        db.session.add(book)
        db.session.commit()
        self.started_at = datetime(2026, 9, 9, 12, 0, 0)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def add_answer(self, outcome, offset=0, value="answer"):
        occurred_at = self.started_at + timedelta(minutes=offset)
        session = GrammarAttemptSession(
            profile_key="test-profile",
            unit_id=self.question.exercise.unit_id,
            status="graded",
            grading_version="test-v1",
            total_questions=1,
            correct_count=int(outcome == "correct"),
            incorrect_count=int(outcome == "incorrect"),
            incomplete_count=int(outcome == "incomplete"),
            unanswered_count=int(outcome == "unanswered"),
            needs_review_count=int(outcome == "needs_review"),
            points_awarded=Decimal("1") if outcome == "correct" else Decimal("0"),
            points_possible=Decimal("1"),
            submitted_at=occurred_at,
        )
        answer = GrammarAttemptAnswer(
            session=session,
            question_id=self.question.id,
            exercise_number="1.1",
            question_number="2",
            question_content_json={"prompt": "Why are you crying?"},
            question_content_sha256="b" * 64,
            solution_snapshot_json={
                "variants": [{"values": {"answer-1": "Why are you crying?"}}]
            },
            solution_sha256="c" * 64,
            user_answers_json={"answer-1": value},
            normalized_answers_json={"answer-1": value},
            outcome=outcome,
            grading_mode="normalized",
            points_awarded=Decimal("1") if outcome == "correct" else Decimal("0"),
            points_possible=Decimal("1"),
        )
        db.session.add(answer)
        db.session.commit()
        return answer

    def test_only_confirmed_incorrect_answers_create_entries(self):
        for index, outcome in enumerate(("unanswered", "incomplete", "needs_review")):
            answer = self.add_answer(outcome, index)
            self.assertIsNone(apply_attempt_answer(answer, "test-profile"))
        db.session.commit()
        self.assertEqual(GrammarMistakeEntry.query.count(), 0)

        wrong = self.add_answer("incorrect", 3, "Why are you cring?")
        apply_attempt_answer(wrong, "test-profile")
        db.session.commit()
        entry = GrammarMistakeEntry.query.one()
        self.assertEqual(entry.status, "reviewing")
        self.assertEqual(entry.wrong_count, 1)

    def test_two_consecutive_correct_answers_master_then_wrong_resets(self):
        wrong = self.add_answer("incorrect", 0, "Why are you cring?")
        apply_attempt_answer(wrong, "test-profile")
        first_correct = self.add_answer("correct", 1, "Why are you crying?")
        apply_attempt_answer(first_correct, "test-profile")
        db.session.commit()
        entry = GrammarMistakeEntry.query.one()
        self.assertEqual((entry.status, entry.correct_streak), ("improving", 1))

        second_correct = self.add_answer("correct", 2, "Why are you crying?")
        apply_attempt_answer(second_correct, "test-profile")
        db.session.commit()
        self.assertEqual((entry.status, entry.correct_streak), ("mastered", 2))
        self.assertIsNotNone(entry.mastered_at)

        wrong_again = self.add_answer("incorrect", 3, "Why is you crying?")
        apply_attempt_answer(wrong_again, "test-profile")
        db.session.commit()
        self.assertEqual((entry.status, entry.correct_streak), ("reviewing", 0))
        self.assertEqual(entry.wrong_count, 2)
        self.assertIsNone(entry.mastered_at)

    def test_backfill_is_idempotent_and_api_shape_uses_wrong_snapshot(self):
        self.add_answer("incorrect", 0, "Why are you cring?")
        sync_existing_attempts()
        sync_existing_attempts()
        entry = GrammarMistakeEntry.query.one()
        self.assertEqual(entry.wrong_count, 1)

        result = list_mistakes("active")
        self.assertEqual(result["summary"]["active"], 1)
        self.assertEqual(result["items"][0]["latest_wrong"]["user_answers"], {
            "answer-1": "Why are you cring?"
        })


if __name__ == "__main__":
    unittest.main()
