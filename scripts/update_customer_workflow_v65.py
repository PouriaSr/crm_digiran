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
PAYLOAD_SHA256 = 'f8e1ad30f20e689bd7febbcafa08a982547359cf4947dc9f8b528c38f2d20731'
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
