"""Self-contained cPanel updater V62: unified interface, printable lists and editable club contracts.
Requires the V61 application source. Place beside manage.py and run with the app Python.
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
nddb5WtArVGrdSVfFv+HPZ7Qu/o3N+e5LA==
"""
PAYLOAD_SHA256 = 'bcdba87321be6a7f2d04918b135a10f8563eeee5a582314f6d7c56ccd68f32d8'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v62_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V62 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v62_update.log'
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
            say('Starting unified interface, printable lists and editable club contracts V62 update.')
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
                    raise RuntimeError('File differs from supported V61 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V61 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V62 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v62-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v62-', dir=path.parent)
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
from customers.club_forms import ClubAccountEditForm, ClubPaymentForm
from customers.club_models import ClubAccount, ClubPayment, LoanProgram
from customers.club_service import purchase_budget, purchase_difference
from django.template.loader import get_template
from django.urls import reverse
assert set(PERMISSIONS) == set(PERMISSION_META)
assert 'customers.club_edit' in PERMISSIONS
assert 'purchase_difference' in dict(ClubPayment.TYPES)
from customers.club_models import ClubAccount
assert all(hasattr(ClubAccount, name) for name in ('loan_purchase_amount','down_payment_amount','main_purchase_amount','purchase_difference_amount','total_customer_payable'))
assert all(hasattr(Ad, name) for name in ('payment_receipt','payment_note','payment_registered_by'))
assert 'data-jdp' in ClubPaymentForm().fields['due_date'].widget.attrs
assert {'loan_program','product','delivery_type','club_fee','status'} <= set(ClubAccountEditForm().fields)
assert reverse('customers:club_account_edit', args=[1]).endswith('/club/account/1/edit/')
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
print('CUSTOMER WORKFLOW V62 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V62 installed, migrations/checks passed, Passenger restart requested.')
            say('Unified form sizing, printable lists and editable club contracts are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v62_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
