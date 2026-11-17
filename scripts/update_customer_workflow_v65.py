"""Self-contained cPanel updater V65: signed purchase differences and case-sourced multi-select loan rules.
Requires the V64 application source. Place beside manage.py and run with the app Python.
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
PAYLOAD_SHA256 = '00eb5dbdbe75d728ee5862e533bbcd9c152d7cc295b34ddfe8263a4b80bec510'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v65_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V65 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v65_update.log'
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
            say('Starting signed purchase differences and case-sourced loan rules V65 update.')
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
                    raise RuntimeError('File differs from supported V64 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V64 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V65 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v65-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v65-', dir=path.parent)
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
assert purchase_difference(azki, 0, 90_000_000) == -5_000_000
assert hasattr(LoanProgram, 'allowed_jobs')
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
from dashboard.templatetags.fa_numbers import signed_fa_num
assert signed_fa_num(-1_500_000).startswith('−')
print('CUSTOMER WORKFLOW V65 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V65 installed, migrations/checks passed, Passenger restart requested.')
            say('Signed purchase differences and multi-select case rules are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v65_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
