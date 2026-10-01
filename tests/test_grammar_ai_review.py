import json
import unittest
from datetime import datetime
from decimal import Decimal

from flask import Flask

from backend.extensions import db
from backend.models.grammar import (
    GrammarAIReviewItem, GrammarAIReviewJob, GrammarAttemptAnswer,
    GrammarAttemptSession, GrammarBook, GrammarExercise, GrammarQuestion, GrammarUnit,
)
from backend.services.grammar_ai_review_service import (
    ReviewResultError, create_review_jobs_for_session, process_review_jobs_once,
    retry_session_review, sync_existing_review_jobs, validate_and_store_result,
)


class FakeMecha:
    def __init__(self, result=None):
        self.result = result
        self.created = []

    def create_task(self, job):
        self.created.append(job.dedup_key)
        return "task-1"

    def get_task(self, task_id):
        return {"id": task_id, "status": "completed", "result": self.result}


class InvalidCreateMechaResponse:
    """Minimal response double for a malformed Mecha create response."""

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    def post(self, *args, **kwargs):
        return self.Response()


class GrammarAIReviewTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            GRAMMAR_AI_REVIEW_BATCH_SIZE=20,
            GRAMMAR_AI_REVIEW_WORKER="grammar-mistake-explainer",
            GRAMMAR_AI_REVIEW_RESULT_MAX_BYTES=100000,
            GRAMMAR_DRAFT_PROFILE="p",
            MECHA_BASE_URL="",
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        book = GrammarBook(slug="book", title="Book", edition="1", source_filename="book.pdf", source_sha256="a" * 64, total_pages=2)
        unit = GrammarUnit(book=book, unit_number=1, title="Present", grammar_point="present", body_source_page=1, exercise_source_page=2, sort_order=1, status="published")
        exercise = GrammarExercise(unit=unit, exercise_number="1.1", instruction="Fill", exercise_type="fill", source_page=2, sort_order=1)
        question = GrammarQuestion(exercise=exercise, question_number="1", question_type="fill", content_json={"prompt": "I __ working."}, source_page=2, sort_order=1)
        session = GrammarAttemptSession(profile_key="p", unit=unit, status="graded", grading_version="v1", total_questions=1, correct_count=0, incorrect_count=1, incomplete_count=0, unanswered_count=0, needs_review_count=0, points_awarded=Decimal("0"), points_possible=Decimal("1"), submitted_at=datetime.utcnow())
        self.answer = GrammarAttemptAnswer(session=session, question=question, exercise_number="1.1", question_number="1", question_content_json=question.content_json, question_content_sha256="b" * 64, solution_snapshot_json={"variants": [{"values": {"answer-1": "am"}}]}, solution_sha256="c" * 64, user_answers_json={"answer-1": "is"}, normalized_answers_json={"answer-1": "is"}, outcome="incorrect", grading_mode="normalized", points_awarded=Decimal("0"), points_possible=Decimal("1"))
        db.session.add(session)
        db.session.commit()
        self.session = session

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def result(self, job, **changes):
        item = {
            "attempt_answer_id": self.answer.id,
            "explanation_status": "explained", "error_type": "verb_form",
            "summary_zh": "be 动词形式错误", "explanation_zh": "I 应搭配 am。",
            "corrected_answers": [{"slot_key": "answer-1", "value": "am"}], "grammar_rule": "I + am",
            "contrast_examples": [{"wrong": "I is", "correct": "I am"}],
            "review_tip_zh": "记住 I am。", "confidence": 0.99,
            "review_decision": "not_applicable",
        }
        item.update(changes)
        return {"schema_version": "grammar-explanation-output/v1", "request_id": job.request_id, "items": [item], "warnings": []}

    def test_creation_and_backfill_are_idempotent(self):
        create_review_jobs_for_session(self.session)
        db.session.commit()
        sync_existing_review_jobs()
        self.assertEqual(GrammarAIReviewJob.query.count(), 1)
        job = GrammarAIReviewJob.query.one()
        self.assertEqual(job.payload_json["items"][0]["accepted_variants"], [{"answer-1": "am"}])

    def test_valid_result_is_stored_without_changing_grade(self):
        job = create_review_jobs_for_session(self.session)[0]
        db.session.flush()
        validate_and_store_result(job, self.result(job))
        db.session.commit()
        self.assertEqual(job.status, "completed")
        self.assertEqual(GrammarAIReviewItem.query.one().summary_zh, "be 动词形式错误")
        self.assertEqual(self.answer.outcome, "incorrect")

    def test_result_must_match_ids_slots_and_grade_boundary(self):
        job = create_review_jobs_for_session(self.session)[0]
        db.session.flush()
        for changes in (
            {"attempt_answer_id": self.answer.id + 1},
            {"corrected_answers": [{"slot_key": "unknown", "value": "am"}]},
            {"corrected_answers": [{"slot_key": "answer-1", "value": "are"}]},
            {"review_decision": "reasonable_variant"},
        ):
            with self.assertRaises(ReviewResultError):
                validate_and_store_result(job, self.result(job, **changes))
        job.payload_json["items"][0]["deterministic_outcome"] = "needs_review"
        with self.assertRaises(ReviewResultError):
            validate_and_store_result(job, self.result(job))

    def test_mecha_create_response_must_be_an_object(self):
        from backend.services.grammar_ai_review_service import MechaClient

        job = create_review_jobs_for_session(self.session)[0]
        client = MechaClient("http://mecha.invalid")
        client.session = InvalidCreateMechaResponse()
        with self.assertRaisesRegex(ReviewResultError, "not an object"):
            client.create_task(job)

    def test_runner_dispatches_then_ingests_and_disabled_runner_is_idle(self):
        job = create_review_jobs_for_session(self.session)[0]
        db.session.commit()
        self.assertEqual(process_review_jobs_once(), {"configured": False, "processed": 0})
        fake = FakeMecha()
        process_review_jobs_once(fake)
        self.assertEqual((job.status, job.mecha_task_id), ("dispatched", "task-1"))
        fake.result = {"output": json.dumps(self.result(job)), "metadata": {"model": "gpt-5.5"}}
        process_review_jobs_once(fake)
        self.assertEqual(job.status, "completed")

    def test_retry_creates_one_new_job_without_overwriting_failure(self):
        original = create_review_jobs_for_session(self.session)[0]
        original.status = "invalid_result"
        original.error_message = "bad output"
        db.session.commit()

        retry_session_review(self.session.id)
        retry_session_review(self.session.id)
        jobs = GrammarAIReviewJob.query.order_by(GrammarAIReviewJob.id).all()
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].status, "invalid_result")
        self.assertEqual(jobs[1].status, "queued")
        self.assertNotEqual(jobs[0].request_id, jobs[1].request_id)


if __name__ == "__main__":
    unittest.main()
