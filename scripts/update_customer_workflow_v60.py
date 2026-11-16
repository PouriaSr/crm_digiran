"""Self-contained cPanel updater V60: club financial snapshot and totals.
Requires the V59 application source. Place beside manage.py and run with the app Python.
It verifies hashes, backs up source and SQLite, migrates, runs checks, and restarts Passenger.
"""
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zlib

PAYLOAD = """
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
"""
PAYLOAD_SHA256 = 'aebbdced5aba2bcf75ed4c6523889e34b67bcc94a252a1276e88d525b12cc29a'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v60_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V60 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v60_update.log'
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as log:
        def say(message):
            print(message, flush=True)
            log.write(message + '\n'); log.flush()
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'crm.settings'
        def run(*args):
            result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError('Command failed: ' + ' '.join(args[:3]))
        try:
            say('Starting club financial snapshot V60 update.')
            packed = base64.b64decode(''.join(PAYLOAD.split()), validate=True)
            if sha(packed) != PAYLOAD_SHA256:
                raise RuntimeError('Script payload is incomplete or changed. Copy the entire script again.')
            specs = json.loads(zlib.decompress(packed))
            updates = {}
            for name, spec in specs.items():
                path = ROOT / name
                if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                    raise RuntimeError('Unsafe file path: ' + name)
                raw = path.read_bytes() if path.exists() else None
                old = raw.replace(b'\r\n', b'\n') if raw is not None else None
                digest = sha(old) if old is not None else None
                if digest == spec['new']:
                    continue
                if digest != spec['old']:
                    raise RuntimeError('File differs from supported V59 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V59 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V60 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v60-' + stamp)
            backup.mkdir(parents=True, mode=0o700); backup.chmod(0o700)
            for name in updates:
                source = ROOT / name
                if source.exists():
                    saved = backup / 'files' / name
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, saved)
            with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as source:
                with sqlite3.connect(backup / 'database.sqlite3') as target:
                    source.backup(target)
                    if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Database backup verification failed.')
            (backup / 'database.sqlite3').chmod(0o600)
            say('Backup created: ' + str(backup))
            for name, content in updates.items():
                path = ROOT / name
                path.parent.mkdir(parents=True, exist_ok=True)
                mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v60-', dir=path.parent)
                try:
                    with os.fdopen(fd, 'wb') as file:
                        file.write(content); file.flush(); os.fsync(file.fileno())
                    os.chmod(temporary, mode)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
            say('Application files updated. Applying migrations and synchronizing tasks...')
            run('manage.py', 'migrate', '--noinput')
            run('manage.py', 'sync_workflow_tasks')
            run('manage.py', 'check')
            run('manage.py', 'migrate', '--check')
            smoke = """import django
django.setup()
from accounts.permissions import PERMISSIONS, PERMISSION_META
from crm.private_files import ClubReceiptStorage
from customers.club_models import ClubAccount, ClubPayment, LoanProgram
from customers.club_service import purchase_budget, purchase_difference
from django.template.loader import get_template
assert set(PERMISSIONS) == set(PERMISSION_META)
assert 'purchase_difference' in dict(ClubPayment.TYPES)
from customers.club_models import ClubAccount
assert all(hasattr(ClubAccount, name) for name in ('loan_purchase_amount','down_payment_amount','purchase_difference_amount','total_customer_payable'))
azki = LoanProgram.objects.get(provider='azki', term_months=12)
assert purchase_budget(azki, 10_000_000) == 72_000_000
assert purchase_difference(azki, 0, 90_000_000) == 28_000_000
ClubPayment.objects.values_list('payment_type', 'amount', 'status').first()
get_template('customers/_club_tab.html')
get_template('customers/_case_tab.html')
try:
    ClubReceiptStorage().url('private')
except ValueError:
    pass
else:
    raise AssertionError('Club receipts must not have public URLs')
print('CUSTOMER WORKFLOW V60 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V60 installed, migrations/checks passed, Passenger restart requested.')
            say('Loan purchase ceiling and the complete customer financial total are stored and displayed.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v60_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
