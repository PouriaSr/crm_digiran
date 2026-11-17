"""Self-contained cPanel updater V63: repeatable smart evaluation, compact contracts and club access controls.
Requires the V62 application source. Place beside manage.py and run with the app Python.
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
PAYLOAD_SHA256 = '825ef1230fd846da40e80fe39938573ffb5529911dae1a598a2ef423ee051dbc'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v63_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V63 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v63_update.log'
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
            say('Starting repeatable smart evaluation, compact contract and club permission V63 update.')
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
                    raise RuntimeError('File differs from supported V62 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V62 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V63 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v63-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v63-', dir=path.parent)
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
print('CUSTOMER WORKFLOW V63 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V63 installed, migrations/checks passed, Passenger restart requested.')
            say('Smart re-evaluation, compact active contracts and editable club permission switches are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v63_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
