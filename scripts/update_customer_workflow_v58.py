"""Self-contained cPanel updater V58: stable feedback, live case timers and purchase differences.
Requires the V57 application source. Place beside manage.py and run with the app Python.
It verifies hashes, backs up source and SQLite, migrates, synchronizes tasks, and restarts Passenger.
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
PAYLOAD_SHA256 = '9d6cb2f2dd246810f817c3f721ecc9410ace5b5660b71d5a69861ad180685b60'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v58_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V58 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v58_update.log'
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
            say('Starting stable feedback, live timer and club difference V58 update.')
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
                    raise RuntimeError('File differs from supported V57 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V57 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V58 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v58-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v58-', dir=path.parent)
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
print('CUSTOMER WORKFLOW V58 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V58 installed, migrations/checks passed, Passenger restart requested.')
            say('Stable inline feedback, second-by-second case timers and receiptable purchase differences are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v58_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
