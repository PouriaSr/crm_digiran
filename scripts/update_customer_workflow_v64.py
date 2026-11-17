"""Self-contained cPanel updater V64: redesigned loan settings, bulk selection and clearer receipt copy.
Requires the V63 application source. Place beside manage.py and run with the app Python.
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
PAYLOAD_SHA256 = '9620d6ce7a3ebfb40e0a509bbb2d330b5b31bbe8e26cfdb0f9f22644183344ef'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v64_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V64 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v64_update.log'
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
            say('Starting redesigned loan settings, bulk actions and receipt wording V64 update.')
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
                    raise RuntimeError('File differs from supported V63 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V63 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V64 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v64-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v64-', dir=path.parent)
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
assert all(key in PERMISSIONS for key in ('customers.club','customers.club_evaluate','customers.club_select','customers.club_edit','customers.club_payment','customers.club_manage'))
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
get_template('customers/_club_evaluation_dialog.html')
loan_settings = get_template('customers/club_program_settings.html')
assert loan_settings
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
print('CUSTOMER WORKFLOW V64 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V64 installed, migrations/checks passed, Passenger restart requested.')
            say('Selectable loan programs, safe bulk actions and corrected receipt wording are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v64_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
