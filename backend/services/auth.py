"""Verified email accounts, Argon2id passwords and revocable cookie sessions.

No seeded accounts, role selection, browser bearer tokens or plaintext passwords.
Mail tokens are hashed at rest; delivery happens after the HTTP response.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from email_validator import validate_email, EmailNotValidError

from backend import schemas as s
from backend.storage import ServiceError, utc_text
from backend.services.exams import identifier


@dataclass(frozen=True)
class AuthSettings:
    public_base_url: str = 'http://127.0.0.1:8000'
    production: bool = False
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = field(default='',repr=False)
    smtp_from: str = ''
    smtp_security: str = 'starttls'

    def __post_init__(self):
        parsed = urlsplit(self.public_base_url)
        if (parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in {'','/'} or parsed.query or parsed.fragment):
            raise ValueError('NIYAMPULSE_PUBLIC_URL must be one canonical HTTP(S) origin')
        if self.production and parsed.scheme != 'https':
            raise ValueError('Production requires an HTTPS NIYAMPULSE_PUBLIC_URL')
        if not self.production and parsed.scheme == 'http' and parsed.hostname not in {'localhost','127.0.0.1','testserver'}:
            raise ValueError('Plain HTTP is limited to native local development')
        if self.smtp_security not in {'ssl','starttls'}:
            raise ValueError('SMTP_SECURITY must be ssl or starttls; plaintext mail is disabled')

    @classmethod
    def from_env(cls):
        hosted = os.environ.get('RENDER') == 'true' or os.environ.get('VERCEL') == '1'
        mode = os.environ.get('NIYAMPULSE_ENV', 'production' if hosted else 'local')
        if mode not in {'local', 'production'}:
            raise ValueError('NIYAMPULSE_ENV must be local or production')
        if hosted and mode != 'production':
            raise ValueError('Hosted runtimes require NIYAMPULSE_ENV=production')
        default_origin = (os.environ.get('RENDER_EXTERNAL_URL')
                          if os.environ.get('RENDER') == 'true' else None)
        return cls(public_base_url=os.environ.get('NIYAMPULSE_PUBLIC_URL') or default_origin or 'http://127.0.0.1:8000',
                   production=mode=='production',
                   smtp_host=os.environ.get('SMTP_HOST',''), smtp_port=int(os.environ.get('SMTP_PORT','587')),
                   smtp_username=os.environ.get('SMTP_USERNAME',''), smtp_password=os.environ.get('SMTP_PASSWORD',''),
                   smtp_from=os.environ.get('SMTP_FROM',''), smtp_security=os.environ.get('SMTP_SECURITY','starttls'))

    @property
    def origin(self): return self.public_base_url.rstrip('/')

    @property
    def cookie_name(self): return '__Host-niyampulse' if self.production else 'niyampulse_session'

    @property
    def allowed_origins(self):
        return {self.origin} if self.production else {self.origin,'http://localhost:5173','http://127.0.0.1:5173'}


class SmtpMailer:
    def __init__(self, settings): self.settings = settings

    @property
    def configured(self):
        settings = self.settings
        return (bool(settings.smtp_host and settings.smtp_from)
                and bool(settings.smtp_username) == bool(settings.smtp_password))

    def send(self, email, purpose, token):
        settings = self.settings
        sender = normalized_email(settings.smtp_from)
        action = 'reset' if purpose == 'RESET' else 'verify'
        subject = 'Reset your NiyamPulse password' if action == 'reset' else 'Finish setting up your NiyamPulse account'
        message = EmailMessage()
        message['From'], message['To'], message['Subject'] = sender, email, subject
        link = settings.origin + '/#' + action + '=' + token
        message.set_content(subject + '\n\nOpen this link to choose your password:\n' + link +
                            '\n\nThis link expires and can be used once. If you did not request it, ignore this email.\nNiyamPulse')
        context = ssl.create_default_context()
        if settings.smtp_security == 'ssl':
            connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
        else:
            connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with connection as client:
            if settings.smtp_security == 'starttls': client.starttls(context=context)
            if settings.smtp_username: client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)


def normalized_email(value):
    try: return validate_email(str(value), check_deliverability=False, allow_smtputf8=False).normalized.casefold()
    except EmailNotValidError:
        raise ServiceError(422,'EMAIL_INVALID','Enter a valid email address') from None


class AuthService:
    def __init__(self, store, *, settings=None, mailer=None, clock=None):
        self.store, self.settings = store, settings or AuthSettings.from_env()
        self.mailer = mailer if mailer is not None else SmtpMailer(self.settings)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self.hash_slots = BoundedSemaphore(4)
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        with self.store.connect(write=True) as con:
            con.execute("INSERT OR IGNORE INTO metadata VALUES ('auth_secret',?)",(secrets.token_hex(32),))
            self.secret = bytes.fromhex(con.execute("SELECT value FROM metadata WHERE key='auth_secret'").fetchone()[0])

    def config(self):
        return s.AuthConfig(registration_available=self.mailer.configured,
                            email_delivery_configured=self.mailer.configured,
                            support_email=os.environ.get('PUBLIC_SUPPORT_EMAIL') or None,
                            deployment_mode='production' if self.settings.production else 'local')

    def check_origin(self, origin):
        if origin not in self.settings.allowed_origins:
            raise ServiceError(403,'ORIGIN_REJECTED','This request must come from the configured application')

    def _digest(self, value): return hashlib.sha256(value.encode()).hexdigest()

    def _rate(self, action, email, address, *, limit=8, window=900):
        now = self.clock().timestamp()
        with self.store.connect(write=True) as con:
            for label, value, maximum in [('address',address,limit*5),('account',email,limit)]:
                key = hmac.new(self.secret,(action+':'+label+':'+value).encode(),hashlib.sha256).hexdigest()
                row = con.execute('SELECT * FROM v2_auth_limits WHERE key=?',(key,)).fetchone()
                count = row['count']+1 if row and now-row['started_at']<window else 1
                start = row['started_at'] if row and now-row['started_at']<window else now
                if count > maximum: raise ServiceError(429,'AUTH_RATE_LIMIT','Too many attempts. Please wait before trying again')
                con.execute('INSERT OR REPLACE INTO v2_auth_limits VALUES (?,?,?)',(key,start,count))
            con.execute('DELETE FROM v2_auth_limits WHERE started_at<?',(now-86400,))

    def _require_mail(self):
        if not self.mailer.configured:
            raise ServiceError(503,'REGISTRATION_UNAVAILABLE','Account email is not configured yet. Please try again later')

    def _token(self, con, user_id, purpose):
        raw = secrets.token_urlsafe(32)
        now = self.clock()
        con.execute('UPDATE v2_auth_tokens SET used_at=? WHERE user_id=? AND purpose=? AND used_at IS NULL',(utc_text(now),user_id,purpose))
        expiry = now+timedelta(minutes=30) if purpose == 'RESET' else now+timedelta(hours=24)
        con.execute('INSERT INTO v2_auth_tokens VALUES (?,?,?,?,NULL)',(self._digest(raw),user_id,purpose,utc_text(expiry)))
        return raw

    def request_registration(self, body, address, *, role='USER'):
        self._require_mail()
        email = normalized_email(body.email)
        self._rate('registration',email,address,limit=3,window=3600)
        with self.store.connect(write=True) as con:
            existing = con.execute('SELECT * FROM v2_credentials WHERE email=?',(email,)).fetchone()
            if existing and existing['email_verified_at']:
                if role=='ADMIN':raise ServiceError(409,'ACCOUNT_EXISTS','Use administrator promotion for an existing verified account')
                return None
            if existing:
                if role == 'ADMIN' and con.execute('SELECT role FROM v2_users WHERE id=?',(existing['user_id'],)).fetchone()[0] != 'ADMIN':
                    raise ServiceError(409,'ACCOUNT_EXISTS','Verify the existing account before using explicit administrator promotion')
                user_id = existing['user_id']
            else:
                user_id = identifier('user')
                now = self.clock()
                profile = s.UserProfileV2(user_id=user_id,display_name=body.display_name or 'Your account',created_at=now,updated_at=now)
                con.execute('INSERT INTO v2_users VALUES (?,?,?,0)',(user_id,role,profile.model_dump_json()))
                con.execute('INSERT INTO v2_credentials(user_id,email,adult_confirmed_at) VALUES (?,?,?)',(user_id,email,utc_text(now)))
            token = self._token(con,user_id,'VERIFY')
        return email,'VERIFY',token

    def request_recovery(self, email, address, *, purpose='RESET'):
        self._require_mail()
        email = normalized_email(email)
        self._rate('email-'+purpose,email,address,limit=3,window=3600)
        with self.store.connect(write=True) as con:
            row = con.execute('SELECT * FROM v2_credentials WHERE email=?',(email,)).fetchone()
            if row is None or (purpose=='RESET' and not row['email_verified_at']) or (purpose=='VERIFY' and row['email_verified_at']): return None
            token = self._token(con,row['user_id'],purpose)
        return email,purpose,token

    def dispatch(self, message):
        if message is None: return
        try:
            self.mailer.send(*message)
            code = 'EMAIL_ACCEPTED_BY_SMTP'
        except Exception:
            # No token, recipient, SMTP response or credentials enter application logs.
            code = 'EMAIL_DELIVERY_FAILED'
        with self.store.connect(write=True) as con:
            con.execute('INSERT INTO v2_auth_events(created_at,event) VALUES (?,?)',(utc_text(self.clock()),code))
        return code=='EMAIL_ACCEPTED_BY_SMTP'

    def _password_hash(self, password):
        if not 15 <= len(password) <= 128: raise ServiceError(422,'PASSWORD_INVALID','Use between 15 and 128 characters')
        if not self.hash_slots.acquire(blocking=False): raise ServiceError(503,'AUTH_BUSY','Please try again shortly')
        try: return self.hasher.hash(password)
        finally: self.hash_slots.release()

    def _password_matches(self, hashed, password):
        if not self.hash_slots.acquire(blocking=False): raise ServiceError(503,'AUTH_BUSY','Please try again shortly')
        try:
            try: return self.hasher.verify(hashed or self.dummy_hash,password)
            except (VerificationError,InvalidHashError): return False
        finally: self.hash_slots.release()

    def complete(self, token, password, *, purpose):
        hashed = self._password_hash(password)
        now = self.clock()
        with self.store.connect(write=True) as con:
            row = con.execute('SELECT * FROM v2_auth_tokens WHERE token_hash=? AND purpose=? AND used_at IS NULL AND expires_at>?',(self._digest(token),purpose,utc_text(now))).fetchone()
            if row is None: raise ServiceError(400,'LINK_INVALID','This link is invalid or expired. Request a new email')
            user_id = row['user_id']
            con.execute('UPDATE v2_auth_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',(utc_text(now),user_id))
            con.execute('UPDATE v2_credentials SET password_hash=?,email_verified_at=coalesce(email_verified_at,?),password_changed_at=? WHERE user_id=?',(hashed,utc_text(now),utc_text(now),user_id))
            con.execute('DELETE FROM v2_auth_sessions WHERE user_id=?',(user_id,))
            con.execute('DELETE FROM v2_sessions WHERE user_id=?',(user_id,))
        return self._issue(user_id,expected_hash=hashed)

    def login(self, email, password, address):
        email = normalized_email(email)
        self._rate('login',email,address,limit=10)
        with self.store.connect() as con:
            row = con.execute('SELECT c.*,u.synthetic FROM v2_credentials c JOIN v2_users u ON u.id=c.user_id WHERE c.email=?',(email,)).fetchone()
        matched = self._password_matches(row['password_hash'] if row else None,password)
        if not row or not matched or not row['email_verified_at'] or row['synthetic']:
            raise ServiceError(401,'LOGIN_FAILED','Email or password is incorrect, or the account has not been verified')
        expected=row['password_hash']
        if self.hasher.check_needs_rehash(expected):
            hashed = self._password_hash(password)
            with self.store.connect(write=True) as con:
                result=con.execute('UPDATE v2_credentials SET password_hash=? WHERE user_id=? AND password_hash=?',(hashed,row['user_id'],expected))
                if not result.rowcount:raise ServiceError(401,'LOGIN_FAILED','Account security changed. Sign in again')
            expected=hashed
        return self._issue(row['user_id'],expected_hash=expected)

    def _issue(self, user_id, *, expected_hash):
        raw = secrets.token_urlsafe(32)
        now = self.clock()
        with self.store.connect(write=True) as con:
            credential=con.execute('SELECT password_hash FROM v2_credentials WHERE user_id=?',(user_id,)).fetchone()
            if credential is None or credential[0]!=expected_hash:raise ServiceError(401,'LOGIN_FAILED','Account security changed. Sign in again')
            con.execute('DELETE FROM v2_auth_sessions WHERE expires_at<=?',(utc_text(now),))
            con.execute('INSERT INTO v2_auth_sessions VALUES (?,?,?,?,?)',(self._digest(raw),user_id,utc_text(now),utc_text(now),utc_text(now+timedelta(hours=8))))
        return raw,self.session(raw)

    def identity(self, raw):
        if not raw: raise ServiceError(401,'SESSION_REQUIRED','Sign in to continue')
        now = self.clock()
        with self.store.connect(write=True) as con:
            row = con.execute('SELECT u.*,c.email,c.email_verified_at,t.expires_at,t.last_seen_at FROM v2_auth_sessions t JOIN v2_users u ON u.id=t.user_id JOIN v2_credentials c ON c.user_id=u.id WHERE t.token_hash=? AND t.expires_at>? AND u.synthetic=0',(self._digest(raw),utc_text(now))).fetchone()
            if row is None or now-datetime.fromisoformat(row['last_seen_at'].replace('Z','+00:00'))>timedelta(minutes=30):
                raise ServiceError(401,'SESSION_EXPIRED','Your session ended. Sign in again')
            if now-datetime.fromisoformat(row['last_seen_at'].replace('Z','+00:00'))>timedelta(minutes=1):
                con.execute('UPDATE v2_auth_sessions SET last_seen_at=? WHERE token_hash=?',(utc_text(now),self._digest(raw)))
            return dict(row)

    def csrf(self, raw): return hmac.new(self.secret,('csrf:'+self._digest(raw)).encode(),hashlib.sha256).hexdigest()

    def check_csrf(self, raw, supplied):
        if not supplied or not hmac.compare_digest(self.csrf(raw),supplied):
            raise ServiceError(403,'CSRF_REQUIRED','Refresh the page before submitting this change')

    def session(self, raw):
        user = self.identity(raw)
        profile = s.UserProfileV2.model_validate_json(user['profile'])
        return s.AuthSession(user_id=user['id'],email=user['email'],display_name=profile.display_name or 'Your account',role=user['role'],email_verified=bool(user['email_verified_at']),expires_at=user['expires_at'],csrf_token=self.csrf(raw))

    def set_cookie(self, response, raw):
        response.set_cookie(self.settings.cookie_name,raw,httponly=True,secure=self.settings.production,
                            samesite='lax',path='/',max_age=8*3600)
        response.headers['Cache-Control'] = 'no-store'

    def logout(self, response, raw):
        if raw:
            with self.store.connect(write=True) as con: con.execute('DELETE FROM v2_auth_sessions WHERE token_hash=?',(self._digest(raw),))
        response.delete_cookie(self.settings.cookie_name,path='/',secure=self.settings.production,httponly=True,samesite='lax')

    def change_password(self, user_id, current, replacement):
        with self.store.connect() as con: row = con.execute('SELECT password_hash FROM v2_credentials WHERE user_id=?',(user_id,)).fetchone()
        if row is None or not self._password_matches(row[0],current): raise ServiceError(401,'PASSWORD_MISMATCH','The current password is incorrect')
        hashed = self._password_hash(replacement)
        with self.store.connect(write=True) as con:
            result=con.execute('UPDATE v2_credentials SET password_hash=?,password_changed_at=? WHERE user_id=? AND password_hash=?',(hashed,utc_text(self.clock()),user_id,row[0]))
            if not result.rowcount:raise ServiceError(409,'PASSWORD_CHANGED','Account security changed. Sign in again')
            con.execute('DELETE FROM v2_auth_sessions WHERE user_id=?',(user_id,))
            con.execute('UPDATE v2_auth_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',(utc_text(self.clock()),user_id))

    def verify_password(self,user_id,password):
        with self.store.connect() as con:row=con.execute('SELECT password_hash FROM v2_credentials WHERE user_id=?',(user_id,)).fetchone()
        if row is None or not self._password_matches(row[0],password):raise ServiceError(401,'PASSWORD_MISMATCH','The current password is incorrect')
