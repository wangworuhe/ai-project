import tempfile
import unittest
from pathlib import Path

from flask import Flask
from werkzeug.security import generate_password_hash

from backend.auth import COOKIE, LIFETIME, install_auth


class AuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000000
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, AUTH_ENABLED=True, AUTH_USERNAME='yala',
                               AUTH_PASSWORD_HASH=generate_password_hash('test-password', method='pbkdf2:sha256:1000'),
                               AUTH_DATABASE_PATH=str(Path(self.temp.name) / 'auth.db'),
                               PUBLIC_ALLOWED_ORIGINS=['https://ai.yalacore.com'])
        install_auth(self.app, clock=lambda: self.now)
        for path in ['/api/grammar/library', '/api/media/audio.mp3', '/api/grammar/book-pages/1']:
            self.app.add_url_rule(path, endpoint=path, view_func=lambda: {'ok': True}, methods=['GET', 'POST'])
        self.app.add_url_rule('/api/health', view_func=lambda: {'status': 'ok'})
        self.client = self.app.test_client()

    def login(self, **kwargs):
        return self.client.post('/api/auth/login', json={'username': 'yala', 'password': 'test-password', **kwargs},
                                headers={'X-Requested-With': 'ai-project'})

    def test_private_resources_and_login_cookie(self):
        for path in ['/api/grammar/library', '/api/media/audio.mp3', '/api/grammar/book-pages/1']:
            self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        response = self.login()
        self.assertEqual(response.status_code, 200)
        cookie = response.headers['Set-Cookie']
        for flag in ['HttpOnly', 'Secure', 'SameSite=Lax', 'Max-Age=5184000']:
            self.assertIn(flag, cookie)
        self.assertEqual(response.json['expires_at'], self.now + LIFETIME)
        self.assertEqual(self.client.get('/api/grammar/library').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/session').headers['Cache-Control'], 'no-store')

    def test_fixed_expiry_and_restart_persistence(self):
        self.login()
        self.now += LIFETIME - 1
        self.assertEqual(self.client.get('/api/auth/session').status_code, 200)
        second = Flask('restart')
        second.config.update(self.app.config)
        install_auth(second, clock=lambda: self.now)
        # Session state is on disk, not in a process-local dictionary.
        restarted = second.test_client()
        token = self.client.get_cookie(COOKIE).value
        restarted.set_cookie(COOKIE, token)
        self.assertEqual(restarted.get('/api/auth/session').status_code, 200)
        self.now += 2
        self.assertEqual(self.client.get('/api/auth/session').status_code, 401)

    def test_csrf_logout_revokes_replayed_cookie(self):
        response = self.login()
        token = self.client.get_cookie(COOKIE).value
        csrf = response.json['csrf_token']
        self.assertEqual(self.client.post('/api/grammar/library').status_code, 403)
        self.assertEqual(self.client.post('/api/grammar/library', headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf}).status_code, 200)
        self.client.set_cookie(COOKIE, token)
        self.assertEqual(self.client.get('/api/grammar/library').status_code, 401)

    def test_login_csrf_and_failure_limit(self):
        self.assertEqual(self.client.post('/api/auth/login', json={'username': 'yala', 'password': 'test-password'}).status_code, 403)
        self.assertEqual(self.client.post('/api/auth/login', json={}, headers={'Origin': 'https://evil.example', 'X-Requested-With': 'ai-project'}).status_code, 403)
        for _ in range(10):
            self.assertEqual(self.login(password='wrong').status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        self.now += 901
        self.assertEqual(self.login().status_code, 200)

    def test_rotation_invalidates_existing_sessions(self):
        self.login()
        token = self.client.get_cookie(COOKIE).value
        second = Flask('rotated')
        second.config.update(self.app.config)
        second.config['AUTH_PASSWORD_HASH'] = generate_password_hash('new-password', method='pbkdf2:sha256:1000')
        install_auth(second, clock=lambda: self.now)
        client = second.test_client()
        client.set_cookie(COOKIE, token)
        self.assertEqual(client.get('/api/auth/session').status_code, 401)

    def test_missing_credentials_fail_closed(self):
        app = Flask('missing')
        app.config.update(AUTH_ENABLED=True)
        with self.assertRaises(RuntimeError):
            install_auth(app)
