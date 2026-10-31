"""Real-account boundary tests with isolated synthetic identities and captured mail."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.exam_store import ExamStore
from backend.tests.local_temp import LocalTemporaryDirectory
from backend.services.auth import AuthSettings


def test_partial_smtp_credentials_keep_registration_disabled(monkeypatch):
    from dataclasses import replace
    from backend.services.auth import SmtpMailer
    settings = AuthSettings(public_base_url='http://testserver', smtp_host='smtp.example.org',
                            smtp_from='sender@example.org', smtp_username='sender@example.org')
    monkeypatch.setattr(SmtpMailer, 'send', lambda *args: pytest.fail('Incomplete SMTP must not send mail'))
    temp = LocalTemporaryDirectory()
    try:
        store = ExamStore(Path(temp.name) / 'smtp-setup.sqlite3')
        app = create_app(store, enable_watchers=False, enable_web_monitor=False,
                         v2_demo=False, auth_settings=settings)
        with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
            config = client.get('/api/v2/auth/config').json()
            assert config['registration_available'] is False
            assert config['email_delivery_configured'] is False
            assert register(client).status_code == 503
        with store.connect() as con:
            assert con.execute('SELECT count(*) FROM v2_users').fetchone()[0] == 0
        assert SmtpMailer(replace(settings, smtp_password='isolated-test-secret')).configured
        assert not SmtpMailer(replace(settings, smtp_username='', smtp_password='isolated-test-secret')).configured
        # Explicitly unauthenticated TLS relays remain supported.
        assert SmtpMailer(replace(settings, smtp_username='')).configured
    finally:
        temp.cleanup()


class RecordingMailer:
    configured = True
    def __init__(self): self.messages = []
    def send(self, email, purpose, token): self.messages.append((email, purpose, token))


def test_trusted_admin_invitation_can_be_retried_without_implicit_promotion(accounts):
    from backend.schemas import RegisterRequest
    from backend.storage import ServiceError
    client, store, mail = accounts
    auth = client.app.state.auth_service
    body = RegisterRequest(email='operator-fixture@example.org', adult_confirmed=True)
    first = auth.request_registration(body, 'trusted-console', role='ADMIN')
    second = auth.request_registration(body, 'trusted-console', role='ADMIN')
    with pytest.raises(ServiceError, match='invalid or expired'):
        auth.complete(first[2], 'isolated administrator password', purpose='VERIFY')
    _, session = auth.complete(second[2], 'isolated administrator password', purpose='VERIFY')
    assert session.role == 'ADMIN'
    pending_user = RegisterRequest(email='pending-user-fixture@example.org', adult_confirmed=True)
    auth.request_registration(pending_user, 'trusted-console')
    with pytest.raises(ServiceError, match='promotion'):
        auth.request_registration(pending_user, 'trusted-console', role='ADMIN')


@pytest.fixture
def accounts():
    temp = LocalTemporaryDirectory()
    mail = RecordingMailer()
    store = ExamStore(Path(temp.name) / 'accounts.sqlite3')
    app = create_app(store, enable_watchers=False, enable_web_monitor=False,
                     v2_demo=False, auth_settings=AuthSettings(public_base_url='http://testserver'), mailer=mail)
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        yield client, store, mail
    temp.cleanup()


def register(client, email='isolated-test@example.org'):
    return client.post('/api/v2/auth/register', json={'email': email, 'display_name': 'Isolated test account', 'adult_confirmed': True})


def activate(client, mail):
    assert register(client).status_code == 202
    token = mail.messages[-1][2]
    response = client.post('/api/v2/auth/verify', json={'token': token, 'password': 'long test password with spaces'})
    assert response.status_code == 200
    return response.json(), token


def test_real_accounts_cannot_select_operator_role(accounts):
    client, store, mail = accounts
    assert client.post('/api/v2/demo/session', json={'persona':'operator'}).status_code == 403
    assert client.post('/api/v2/auth/register', json={'email':'isolated-test@example.org','display_name':'test','adult_confirmed':True,'role':'ADMIN'}).status_code == 422
    session, token = activate(client, mail)
    assert session['role'] == 'USER' and session['email_verified']
    assert 'access_token' not in session
    assert client.get('/api/v2/admin/dashboard').status_code == 403
    with store.connect() as con:
        assert con.execute('SELECT synthetic FROM v2_users').fetchone()[0] == 0
        assert 'long test password' not in con.execute('SELECT password_hash FROM v2_credentials').fetchone()[0]


def test_session_csrf_logout_and_token_single_use(accounts):
    client, store, mail = accounts
    session, token = activate(client, mail)
    assert 'HttpOnly' in str(client.cookies) or client.cookies.get('niyampulse_session')
    assert client.post('/api/v2/auth/verify',json={'token':token,'password':'another sufficiently long password'}).status_code == 400
    assert client.post('/api/v2/me/subscriptions',json={'cycle_id':'jee-main:2027:s1'}).status_code == 403
    headers={'X-CSRF-Token':session['csrf_token']}
    assert client.post('/api/v2/me/subscriptions',headers=headers,json={'cycle_id':'jee-main:2027:s1'}).status_code in {200,201}
    assert client.post('/api/v2/auth/logout',headers=headers).status_code == 204
    assert client.get('/api/v2/auth/session').status_code == 401


def test_bad_origin_and_underage_declaration_fail_closed(accounts):
    client, _, mail = accounts
    assert client.post('/api/v2/auth/register',headers={'Origin':'https://evil.example'},json={'email':'isolated-test@example.org','adult_confirmed':True}).status_code == 403
    assert client.post('/api/v2/auth/register',json={'email':'isolated-test@example.org','adult_confirmed':False}).status_code == 422
    assert not mail.messages


def test_real_subscription_backfills_only_reviewed_real_notices(accounts):
    from datetime import datetime,timezone
    from backend import schemas as s
    from backend.services.exams import ExamService
    from backend.services.source_monitor import SourceMonitor,parse_listing,FetchResult
    client,store,mail=accounts
    account,_=activate(client,mail)
    root=Path(__file__).parent/'fixtures/official'
    publisher=next(item for item in store.sources() if item.source_id=='upsc-active')
    listing=(root/'upsc-listing.html').read_bytes()
    link=next(item for item in parse_listing(publisher,listing) if item.cycle_id=='upsc-ese:2027')
    notice,_=SourceMonitor(store).ingest(publisher,link,FetchResult(link.url,link.url,(root/'upsc-ese-2027.html').read_bytes(),'text/html',200),listing=FetchResult(str(publisher.listing_url),str(publisher.listing_url),listing,'text/html',200))
    ExamService(store).review(notice.notice_id,s.NoticeReviewDecision(notice_id=notice.notice_id,reviewer_id='isolated-fixture-reviewer',action='APPROVE',reason='Isolated captured-source fixture acceptance',reviewed_at=datetime.now(timezone.utc),expected_revision=0),'isolated-fixture-reviewer')
    for _ in range(2):assert client.post('/api/v2/me/subscriptions',headers={'X-CSRF-Token':account['csrf_token']},json={'cycle_id':notice.cycle_id}).status_code in {200,201}
    inbox=client.get('/api/v2/me/notifications').json()
    assert len(inbox['notifications'])==1
    assert inbox['notifications'][0]['official_source_url']==link.url


def test_reset_is_single_use_and_revokes_prior_sessions(accounts):
    client,store,mail=accounts
    session,_=activate(client,mail)
    prior=client.cookies.get('niyampulse_session')
    known=client.post('/api/v2/auth/forgot-password',json={'email':'isolated-test@example.org'})
    token=mail.messages[-1][2]
    unknown=client.post('/api/v2/auth/forgot-password',json={'email':'missing-test@example.org'})
    assert known.status_code==unknown.status_code==202 and known.json()==unknown.json()
    assert client.post('/api/v2/auth/verify',json={'token':token,'password':'new long password for testing'}).status_code==400
    changed=client.post('/api/v2/auth/reset-password',json={'token':token,'password':'new long password for testing'})
    assert changed.status_code==200
    assert client.post('/api/v2/auth/reset-password',json={'token':token,'password':'yet another sufficiently long password'}).status_code==400
    client.cookies.clear();client.cookies.set('niyampulse_session',prior)
    assert client.get('/api/v2/auth/session').status_code==401
    assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'long test password with spaces'}).status_code==401
    assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'new long password for testing'}).status_code==200
    with store.connect() as con:
        assert con.execute('SELECT 1 FROM v2_auth_tokens WHERE token_hash=?',(token,)).fetchone() is None


def test_password_spaces_survive_and_cookie_is_httponly(accounts):
    client,_,mail=accounts
    assert register(client).status_code==202
    response=client.post('/api/v2/auth/verify',json={'token':mail.messages[-1][2],'password':'  a long untrimmed passphrase  '})
    assert response.status_code==200
    cookie=response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie and 'Path=/' in cookie
    client.cookies.clear()
    assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'a long untrimmed passphrase'}).status_code==401
    assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'  a long untrimmed passphrase  '}).status_code==200


def test_idle_expiry_and_action_expiry(accounts):
    from datetime import timedelta
    client,_,mail=accounts
    session,_=activate(client,mail)
    auth=client.app.state.auth_service;now=auth.clock()
    auth.clock=lambda:now+timedelta(minutes=31)
    assert client.get('/api/v2/auth/session').status_code==401
    client.cookies.clear()
    assert register(client,'second-test@example.org').status_code==202
    token=mail.messages[-1][2]
    auth.clock=lambda:now+timedelta(hours=26)
    assert client.post('/api/v2/auth/verify',json={'token':token,'password':'another long testing passphrase'}).status_code==400


def test_password_change_and_deletion_require_current_password(accounts):
    client,store,mail=accounts
    session,_=activate(client,mail);headers={'X-CSRF-Token':session['csrf_token']}
    assert client.request('DELETE','/api/v2/me/account',headers=headers,json={'password':'wrong password'}).status_code==401
    assert client.post('/api/v2/auth/password',headers=headers,json={'current_password':'long test password with spaces','new_password':'replacement long test password'}).status_code==204
    assert client.get('/api/v2/auth/session').status_code==401
    logged=client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'replacement long test password'}).json()
    assert client.request('DELETE','/api/v2/me/account',headers={'X-CSRF-Token':logged['csrf_token']},json={'password':'replacement long test password'}).status_code==204
    with store.connect() as con:
        for table in ['v2_users','v2_credentials','v2_auth_sessions','v2_auth_tokens']:assert con.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_login_throttle_and_request_limit(accounts):
    client,_,mail=accounts
    activate(client,mail);client.cookies.clear()
    for _ in range(10):assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'incorrect password'}).status_code==401
    assert client.post('/api/v2/auth/login',json={'email':'isolated-test@example.org','password':'incorrect password'}).status_code==429
    assert client.post('/api/v2/auth/login',content=b' '*9000,headers={'Content-Type':'application/json'}).status_code==413


def test_legacy_private_apis_require_admin_and_headers_are_present(accounts):
    client,_,mail=accounts
    assert client.get('/api/v1/workspaces/private').status_code==401
    activate(client,mail)
    assert client.get('/api/v1/workspaces/private').status_code==403
    response=client.get('/api/v2/catalog')
    assert response.headers['X-Frame-Options']=='DENY'
    assert response.headers['Referrer-Policy']=='no-referrer'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']


def test_old_password_verification_cannot_create_session_after_concurrent_reset(accounts):
    from backend.storage import ServiceError
    client,store,mail=accounts
    activate(client,mail);auth=client.app.state.auth_service
    original=auth._password_matches
    def reset_during_verification(hashed,password):
        result=original(hashed,password)
        new=auth._password_hash('concurrently reset long password')
        with store.connect(write=True) as con:con.execute('UPDATE v2_credentials SET password_hash=?',(new,))
        return result
    auth._password_matches=reset_during_verification
    with pytest.raises(ServiceError,match='security changed'):auth.login('isolated-test@example.org','long test password with spaces','test-address')


def test_production_cookie_requires_https_and_sets_security_attributes():
    with pytest.raises(ValueError,match='HTTPS'):AuthSettings(public_base_url='http://testserver',production=True)
    temp=LocalTemporaryDirectory();mail=RecordingMailer()
    try:
        app=create_app(ExamStore(Path(temp.name)/'secure.sqlite3'),enable_watchers=False,enable_web_monitor=False,v2_demo=False,
                       auth_settings=AuthSettings(public_base_url='https://testserver',production=True),mailer=mail)
        with TestClient(app,base_url='https://testserver',headers={'Origin':'https://testserver'}) as client:
            assert register(client).status_code==202
            response=client.post('/api/v2/auth/verify',json={'token':mail.messages[-1][2],'password':'secure production test passphrase'})
            assert response.status_code==200
            cookie=response.headers['set-cookie']
            assert '__Host-niyampulse=' in cookie and 'Secure' in cookie and 'HttpOnly' in cookie and 'Domain=' not in cookie
            assert client.get('/api/v2/auth/session').status_code==200
            assert response.headers['Strict-Transport-Security'].startswith('max-age=')
    finally:temp.cleanup()


def test_environment_never_enables_demo_role_impersonation(monkeypatch):
    monkeypatch.setenv('NIYAMPULSE_V2_DEMO','1')
    temp=LocalTemporaryDirectory()
    try:
        store=ExamStore(Path(temp.name)/'default.sqlite3')
        with TestClient(create_app(store,enable_watchers=False,enable_web_monitor=False,auth_settings=AuthSettings(public_base_url='http://testserver')),headers={'Origin':'http://testserver'}) as client:
            assert client.post('/api/v2/demo/session',json={'persona':'operator'}).status_code==403
            assert not client.get('/api/v2/status').json()['demo_mode']
        with store.connect() as con:assert con.execute('SELECT count(*) FROM v2_users').fetchone()[0]==0
    finally:temp.cleanup()
