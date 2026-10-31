"""Deployment boundaries and recovery use isolated local databases, never real mail."""
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.exam_store import ExamStore
from backend.main import create_app
from backend.services.auth import AuthSettings
from backend.tests.local_temp import LocalTemporaryDirectory


@contextmanager
def local_store():
    temp = LocalTemporaryDirectory()
    try:
        yield ExamStore(Path(temp.name) / 'state.sqlite3')
    finally:
        temp.cleanup()


def test_health_readiness_reports_dependency_failure_without_details(monkeypatch):
    with local_store() as store:
        app = create_app(store, enable_watchers=False, enable_web_monitor=False,
                         auth_settings=AuthSettings(public_base_url='http://testserver'))
        with TestClient(app) as client:
            assert client.get('/api/v2/health/live').status_code == 200
            healthy = client.get('/api/v2/health/ready')
            assert healthy.status_code == 200
            assert healthy.json()['checks']['database']
            def broken(*args, **kwargs):
                raise sqlite3.OperationalError('private database details must not escape')
            with monkeypatch.context() as scoped:
                scoped.setattr(store, 'connect', broken)
                unhealthy = client.get('/api/v2/health/ready')
                assert unhealthy.status_code == 503
                assert unhealthy.json()['status'] == 'NOT_READY'
                assert not unhealthy.json()['checks']['database']
                assert 'private database' not in unhealthy.text


def test_public_api_body_is_bounded_before_validation():
    with local_store() as store:
        with TestClient(create_app(store, enable_watchers=False, enable_web_monitor=False,
                                  auth_settings=AuthSettings(public_base_url='http://testserver'))) as client:
            response = client.patch('/api/v2/me/profile', json={'display_name': 'x' * (300 * 1024)})
            assert response.status_code == 413
            assert response.json()['code'] == 'REQUEST_TOO_LARGE'
            assert response.json()['request_id']


def test_unknown_environment_does_not_fall_back_to_local(monkeypatch):
    monkeypatch.setenv('NIYAMPULSE_ENV', 'prod-typo')
    with pytest.raises(ValueError, match='NIYAMPULSE_ENV'):
        AuthSettings.from_env()


def test_production_has_no_interactive_api_docs():
    with local_store() as store:
        with TestClient(create_app(store, enable_watchers=False, enable_web_monitor=False,
                                  auth_settings=AuthSettings(public_base_url='https://testserver', production=True)),
                        base_url='https://testserver') as client:
            for path in ['/docs', '/redoc', '/openapi.json']:
                assert client.get(path).status_code == 404


def test_render_defaults_to_production_and_its_actual_origin(monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://isolated-fixture.onrender.com')
    monkeypatch.delenv('NIYAMPULSE_ENV', raising=False)
    monkeypatch.delenv('NIYAMPULSE_PUBLIC_URL', raising=False)
    settings = AuthSettings.from_env()
    assert settings.production and settings.origin == 'https://isolated-fixture.onrender.com'
    monkeypatch.setenv('NIYAMPULSE_ENV', 'local')
    with pytest.raises(ValueError, match='production'):
        AuthSettings.from_env()


def test_runtime_lock_releases_after_failure():
    from backend.operations import RuntimeLock
    with local_store() as store:
        path = store.path.parent / 'runtime.lock'
        with pytest.raises(RuntimeError, match='intentional'):
            with RuntimeLock(path):
                with pytest.raises(RuntimeError, match='already running'):
                    with RuntimeLock(path):
                        pytest.fail('Duplicate runtime acquired the lock')
                raise RuntimeError('intentional')
        with RuntimeLock(path):
            pass


def test_backup_restore_preserves_evidence_and_budget_but_revokes_tokens():
    from backend.operations import backup_database, restore_database
    from backend.services.auth import AuthService
    from backend.schemas import RegisterRequest
    from tests.test_auth import RecordingMailer
    with local_store() as store:
        auth = AuthService(store, settings=AuthSettings(public_base_url='http://testserver'), mailer=RecordingMailer())
        message = auth.request_registration(RegisterRequest(email='backup-fixture@example.org',adult_confirmed=True),'isolated-test')
        auth.complete(message[2], 'isolated password for backup testing', purpose='VERIFY')
        with store.connect(write=True) as con:
            con.execute("INSERT INTO metadata VALUES ('recovery-proof','immutable-source-test')")
            con.execute('UPDATE v2_ai_budget SET limit_paise=5000 WHERE id=1')
            con.execute("INSERT INTO v2_ai_calls(id,cache_key,credential_fingerprint,started_at,status,reserved_paise) VALUES('fixture-call','fixture-cache','not-a-real-credential','2026-10-30T00:00:00Z','TEST_ONLY',5000)")
            assert con.execute('SELECT count(*) FROM v2_auth_sessions').fetchone()[0] == 1
        archive = backup_database(store.path, store.path.parent / 'backups')
        with closing(sqlite3.connect(archive)) as con:
            original = con.execute('SELECT * FROM v2_ai_budget').fetchall()
        target = store.path.parent / 'restored' / 'niyampulse.sqlite3'
        restore_database(archive, target)
        with closing(sqlite3.connect(target)) as con:
            assert con.execute("SELECT value FROM metadata WHERE key='recovery-proof'").fetchone()[0] == 'immutable-source-test'
            assert con.execute('SELECT * FROM v2_ai_budget').fetchall() == original
            assert not con.execute('PRAGMA foreign_key_check').fetchall()
            assert not con.execute('SELECT count(*) FROM v2_auth_sessions').fetchone()[0]
            assert not con.execute('SELECT count(*) FROM v2_auth_tokens').fetchone()[0]
            assert con.execute('SELECT sum(reserved_paise) FROM v2_ai_calls').fetchone()[0] == 5000
        with pytest.raises(ValueError, match='already exists'):
            restore_database(archive, target)
        assert store.path.exists()


def test_restore_rejects_corrupted_backup_before_creating_target():
    from backend.operations import backup_database, restore_database
    with local_store() as store:
        archive = backup_database(store.path, store.path.parent / 'backups')
        with archive.open('ab') as handle:
            handle.write(b'corruption-fixture')
        target = store.path.parent / 'refused' / 'niyampulse.sqlite3'
        with pytest.raises(ValueError, match='checksum'):
            restore_database(archive, target)
        assert not target.exists()


def test_production_rejects_ephemeral_deployments(monkeypatch):
    from backend.operations import validate_deployment
    settings = AuthSettings(public_base_url='https://example.org', production=True,
                            smtp_host='smtp.example.org', smtp_from='sender@example.org')
    with local_store() as store:
        monkeypatch.setenv('NIYAMPULSE_DATA_DIR', str(store.path.parent))
        monkeypatch.delenv('NIYAMPULSE_STORAGE_DURABLE', raising=False)
        with pytest.raises(ValueError, match='STORAGE_DURABLE'):
            validate_deployment(settings)
        monkeypatch.setenv('NIYAMPULSE_STORAGE_DURABLE', '1')
        monkeypatch.setenv('VERCEL', '1')
        with pytest.raises(ValueError, match='serverless'):
            validate_deployment(settings)


def test_default_production_app_holds_the_runtime_lock(monkeypatch):
    from backend.operations import RuntimeLock
    with local_store() as store:
        monkeypatch.setenv('NIYAMPULSE_DATA_DIR', str(store.path.parent))
        monkeypatch.setenv('NIYAMPULSE_STORAGE_DURABLE', '1')
        monkeypatch.setenv('NIYAMPULSE_V2_DEMO', '0')
        settings = AuthSettings(public_base_url='https://testserver', production=True,
                                smtp_host='smtp.example.org', smtp_from='sender@example.org')
        with TestClient(create_app(enable_watchers=False, enable_web_monitor=False,
                                  auth_settings=settings), base_url='https://testserver') as client:
            assert client.get('/api/v2/health/ready').status_code == 200
            with pytest.raises(RuntimeError, match='already running'):
                with RuntimeLock(store.path.parent / '.runtime.lock'):
                    pytest.fail('The live production app did not hold its lock')
        with RuntimeLock(store.path.parent / '.runtime.lock'):
            pass

