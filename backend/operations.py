"""Local release checks and SQLite backup/recovery; never print credentials."""
import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import ssl
import smtplib
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


class RuntimeLock:
    """OS-owned advisory lock; automatically released when a process exits."""
    def __init__(self, path):
        self.path, self.handle = Path(path), None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open('a+b')
        self.handle.seek(0, 2)
        if not self.handle.tell():
            self.handle.write(b'0'); self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close(); self.handle = None
            raise RuntimeError('A production API or monitor is already running for this data directory') from None
        return self

    def __exit__(self, *args):
        if self.handle is None: return
        try:
            self.handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close(); self.handle = None


def validate_deployment(settings):
    if not settings.production: return
    if os.environ.get('VERCEL') == '1':
        raise ValueError('This SQLite/background-worker architecture cannot run as serverless functions')
    if os.environ.get('NIYAMPULSE_STORAGE_DURABLE') != '1':
        raise ValueError('Production requires NIYAMPULSE_STORAGE_DURABLE=1 after verifying persistent storage')
    raw = os.environ.get('NIYAMPULSE_DATA_DIR', '')
    if not raw or not Path(raw).is_absolute():
        raise ValueError('Production requires an explicit absolute NIYAMPULSE_DATA_DIR')
    if os.environ.get('NIYAMPULSE_V2_DEMO', '0') != '0':
        raise ValueError('Production must have NIYAMPULSE_V2_DEMO=0')
    if os.environ.get('RENDER') == 'true':
        root = Path(os.environ.get('NIYAMPULSE_PERSISTENT_ROOT', '/var/data')).resolve()
        if not root.is_mount() or not Path(raw).resolve().is_relative_to(root):
            raise ValueError('Render requires an attached persistent disk and a data directory inside its mount')
    from backend.services.auth import SmtpMailer
    if not SmtpMailer(settings).configured:
        raise ValueError('Production account email requires complete SMTP configuration')


@contextmanager
def production_runtime(settings, *, enforce=True):
    if not settings.production or not enforce:
        yield
        return
    validate_deployment(settings)
    with RuntimeLock(Path(os.environ['NIYAMPULSE_DATA_DIR']) / '.runtime.lock'):
        yield


def readiness_checks(app):
    checks = {'database': False, 'frontend': (ROOT / 'frontend/dist/index.html').is_file()}
    try:
        with app.state.exam_store.connect() as con:
            checks['database'] = bool(con.execute('SELECT 1 FROM v2_migrations WHERE version=6').fetchone())
    except (sqlite3.Error, OSError):
        pass
    schedulers = [app.state.web_scheduler, app.state.processing_scheduler]
    checks['background_workers'] = all(item is None or item.thread.is_alive() for item in schedulers)
    return checks


@contextmanager
def _readonly(path):
    path = Path(path).resolve()
    if not path.is_file(): raise ValueError('Database file is missing; no empty replacement was created')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    try:
        yield connection
    finally:
        connection.close()


def _verify(con):
    if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Database integrity verification failed')
    if not con.execute('SELECT 1 FROM v2_migrations WHERE version=6').fetchone():
        raise ValueError('Database account migration is missing')


def backup_database(source, directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    destination = directory / ('niyampulse-' + stamp + '-' + uuid.uuid4().hex[:8] + '.sqlite3')
    # Exclusive creation prevents accidental reuse of an existing backup.
    destination.open('xb').close()
    try:
        with _readonly(source) as original, closing(sqlite3.connect(destination)) as archive:
            original.backup(archive)
            _verify(archive)
        with destination.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        destination.with_suffix('.manifest.json').write_text(json.dumps({
            'created_at': datetime.now(timezone.utc).isoformat(), 'sha256': digest,
            'database_file': destination.name, 'format': 'sqlite-online-backup-v1',
        }, indent=2), encoding='utf-8')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def restore_database(archive, target):
    archive, target = Path(archive).resolve(), Path(target).resolve()
    if target.exists(): raise ValueError('Restore target already exists; it will not be overwritten')
    manifest = archive.with_suffix('.manifest.json')
    if not manifest.is_file(): raise ValueError('A verified backup manifest is required')
    with archive.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if json.loads(manifest.read_text(encoding='utf-8'))['sha256'] != digest:
        raise ValueError('Backup checksum does not match its manifest')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.open('xb').close()
    try:
        with _readonly(archive) as original, closing(sqlite3.connect(target)) as restored:
            original.backup(restored)
            _verify(restored)
            for table in ['v2_auth_sessions', 'v2_sessions', 'v2_auth_tokens']:
                restored.execute('DELETE FROM ' + table)
            restored.commit()
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def check_smtp(settings):
    """TLS + authentication only: does not send a message or read the mailbox."""
    from backend.services.auth import SmtpMailer
    if not SmtpMailer(settings).configured: raise ValueError('SMTP_SETTINGS_INCOMPLETE')
    try:
        context = ssl.create_default_context()
        connection = (smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
                      if settings.smtp_security == 'ssl' else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15))
        with connection as client:
            client.ehlo()
            if settings.smtp_security == 'starttls': client.starttls(context=context); client.ehlo()
            if settings.smtp_username: client.login(settings.smtp_username, settings.smtp_password)
    except smtplib.SMTPAuthenticationError:
        raise ValueError('SMTP_AUTHENTICATION_FAILED; inspect the credential privately') from None
    except (OSError, smtplib.SMTPException):
        raise ValueError('SMTP_CONNECTION_FAILED; no credential details logged') from None


def preflight(settings, data_dir):
    checks = {'python_312': sys.version_info[:2] == (3, 12),
              'frontend_built': (ROOT / 'frontend/dist/index.html').is_file(),
              'database_integrity': False, 'verified_administrator': False,
              'no_synthetic_accounts_or_notices': False, 'spending_ledger_present': False}
    from backend.services.auth import SmtpMailer
    checks['smtp_configured'] = SmtpMailer(settings).configured
    try:
        validate_deployment(settings)
        checks['deployment_configuration'] = True
    except ValueError:
        checks['deployment_configuration'] = False
    try:
        with _readonly(Path(data_dir) / 'niyampulse.sqlite3') as con:
            _verify(con)
            checks['database_integrity'] = True
            checks['verified_administrator'] = bool(con.execute("SELECT 1 FROM v2_users u JOIN v2_credentials c ON c.user_id=u.id WHERE u.synthetic=0 AND u.role='ADMIN' AND c.email_verified_at IS NOT NULL LIMIT 1").fetchone())
            checks['no_synthetic_accounts_or_notices'] = not (con.execute('SELECT 1 FROM v2_users WHERE synthetic=1 LIMIT 1').fetchone() or con.execute("SELECT 1 FROM v2_notices WHERE json_extract(payload,'$.source_kind')='LOCAL_DEMO_FIXTURE' LIMIT 1").fetchone())
            checks['spending_ledger_present'] = bool(con.execute('SELECT 1 FROM v2_ai_budget WHERE id=1').fetchone())
    except (ValueError, OSError, sqlite3.Error):
        pass
    return {'status': 'READY' if all(checks.values()) else 'NOT_READY',
            'mode': 'production' if settings.production else 'local', 'checks': checks}


def main():
    from dotenv import load_dotenv
    from backend.services.auth import AuthSettings
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'smtp-check', 'backup', 'restore'])
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'var/backups')
    parser.add_argument('--from-backup', type=Path)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    settings = AuthSettings.from_env()
    try:
        if args.action == 'smtp-check':
            check_smtp(settings); print('SMTP_TLS_AND_AUTHENTICATION_OK; no message sent')
        elif args.action == 'preflight':
            result = preflight(settings, Path(os.environ.get('NIYAMPULSE_DATA_DIR', 'var/production')))
            print(json.dumps(result, indent=2))
            if result['status'] != 'READY': raise SystemExit(1)
        elif args.action == 'backup':
            print(backup_database(Path(os.environ.get('NIYAMPULSE_DATA_DIR', 'var/production')) / 'niyampulse.sqlite3', args.output_dir))
        else:
            if not args.from_backup or not args.target: parser.error('restore requires --from-backup and --target (a new database file)')
            print(restore_database(args.from_backup, args.target))
    except (ValueError, OSError, sqlite3.Error):
        # Do not print exception values from network/database/secret-file libraries.
        raise SystemExit('OPERATION_FAILED; verify the configured paths, storage and private settings') from None


if __name__ == '__main__': main()
