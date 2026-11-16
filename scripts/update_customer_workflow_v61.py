"""Self-contained cPanel updater V61: corrected club formula and private payment receipts.
Requires the V60 application source. Place beside manage.py and run with the app Python.
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
PAYLOAD_SHA256 = '57ee52a06010f6a85b372e801caf8f28d7c3021c3760049d227b7c6960bf3842'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v61_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V61 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v61_update.log'
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
            say('Starting corrected club finance and payment receipts V61 update.')
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
                    raise RuntimeError('File differs from supported V60 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V60 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V61 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v61-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v61-', dir=path.parent)
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
from ads.models import Ad
from crm.private_files import AdReceiptStorage, ClubReceiptStorage
from customers.club_forms import ClubPaymentForm
from customers.club_models import ClubAccount, ClubPayment, LoanProgram
from customers.club_service import purchase_budget, purchase_difference
from django.template.loader import get_template
assert set(PERMISSIONS) == set(PERMISSION_META)
assert 'purchase_difference' in dict(ClubPayment.TYPES)
from customers.club_models import ClubAccount
assert all(hasattr(ClubAccount, name) for name in ('loan_purchase_amount','down_payment_amount','main_purchase_amount','purchase_difference_amount','total_customer_payable'))
assert all(hasattr(Ad, name) for name in ('payment_receipt','payment_note','payment_registered_by'))
assert 'data-jdp' in ClubPaymentForm().fields['due_date'].widget.attrs
azki = LoanProgram.objects.get(provider='azki', term_months=12)
assert purchase_budget(azki, 10_000_000) == 72_000_000
assert purchase_difference(azki, 0, 79_000_000) == 6_000_000
ClubPayment.objects.values_list('payment_type', 'amount', 'status').first()
get_template('customers/_club_tab.html')
get_template('customers/club_program_settings.html')
get_template('customers/_case_tab.html')
try:
    ClubReceiptStorage().url('private')
except ValueError:
    pass
else:
    raise AssertionError('Club receipts must not have public URLs')
try:
    AdReceiptStorage().url('private')
except ValueError:
    pass
else:
    raise AssertionError('Advertising receipts must not have public URLs')
print('CUSTOMER WORKFLOW V61 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V61 installed, migrations/checks passed, Passenger restart requested.')
            say('Corrected loan formula and private club/advertising payment receipts are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v61_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
