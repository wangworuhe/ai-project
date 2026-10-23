import unittest
from threading import Event, Lock, Thread

from flask import Flask

from backend.public_guard import install_public_guard


class PublicGuardTest(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.calls = 0
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            PUBLIC_ACCESS_ENABLED=True,
            PUBLIC_ALLOWED_ORIGINS=["https://ai.yalacore.com"],
            MAX_CONTENT_LENGTH=100,
        )
        install_public_guard(self.app, clock=lambda: self.now)

        def paid():
            self.calls += 1
            return {"ok": True}

        self.app.add_url_rule("/api/tts/synthesize", view_func=paid, methods=["POST"])
        self.app.add_url_rule("/api/health", view_func=lambda: {"status": "ok"})
        self.client = self.app.test_client()

    def test_cross_site_requests_never_reach_paid_handler(self):
        for headers in [
            {"Origin": "https://attacker.example"},
            {"Sec-Fetch-Site": "cross-site"},
        ]:
            self.assertEqual(self.client.post("/api/tts/synthesize", headers=headers).status_code, 403)
        self.assertEqual(self.calls, 0)
        self.assertEqual(self.client.post(
            "/api/tts/synthesize", headers={"Origin": "https://ai.yalacore.com"}
        ).status_code, 200)

    def test_oversized_upload_is_rejected_before_handler(self):
        response = self.client.post("/api/tts/synthesize", data=b"x" * 101)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.calls, 0)

    def test_minute_budget_recovers_and_does_not_block_health(self):
        for _ in range(10):
            self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 200)
        response = self.client.post("/api/tts/synthesize")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertEqual(self.calls, 10)
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.now = 61
        self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 200)

    def test_hour_budget_cannot_be_bypassed_by_waiting_each_minute(self):
        for minute in range(12):
            self.now = minute * 61
            for _ in range(10):
                self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 200)
        self.now += 61
        self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 429)
        self.now = 3601
        self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 200)

    def test_long_tts_text_is_bounded_even_when_body_limit_is_larger(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 20000
        response = self.client.post("/api/tts/synthesize", json={"text": "x" * 10001})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.calls, 0)

    def test_two_in_flight_calls_block_a_third_and_release_afterwards(self):
        ready = Event()
        release = Event()
        started = []
        counter_lock = Lock()

        def hold():
            with counter_lock:
                started.append(True)
                if len(started) == 2:
                    ready.set()
            release.wait(5)
            return {"ok": True}

        self.app.view_functions["paid"] = hold

        def call():
            with self.app.test_client() as client:
                client.post("/api/tts/synthesize")

        threads = [Thread(target=call) for _ in range(2)]
        try:
            for thread in threads:
                thread.start()
            self.assertTrue(ready.wait(3))
            self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 429)
        finally:
            release.set()
            for thread in threads:
                thread.join(3)
        self.assertEqual(self.client.post("/api/tts/synthesize").status_code, 200)
