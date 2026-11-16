"""Self-contained cPanel updater V57: loan evaluation and customer club.
Requires the V56 application source. Place beside manage.py and run with the app Python.
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
4f+pDaNA==
"""
PAYLOAD_SHA256 = '6521d65beae82d1443ab2f84d7d4bb4fd6d60310e9e94155037986128b7edc05'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v57_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V57 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v57_update.log'
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
            say('Starting customer loan and club workflow V57 update.')
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
                    raise RuntimeError('File differs from supported V56 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V56 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V57 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v57-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v57-', dir=path.parent)
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
            run('-c', "import django\ndjango.setup()\nfrom accounts.permissions import PERMISSIONS, PERMISSION_META\nfrom crm.private_files import ClubReceiptStorage\nfrom customers.club_models import ClubAccount, ClubPayment, LoanEvaluation, LoanProgram\nfrom customers.models import CustomerCase\nfrom django.template.loader import get_template\nfrom hr.models import Task\nassert set(PERMISSIONS) == set(PERMISSION_META)\nassert all(key in PERMISSIONS for key in ('customers.club','customers.club_evaluate','customers.club_select','customers.club_payment','customers.club_manage'))\nassert LoanProgram.objects.filter(is_active=True).count() >= 9\nfrom customers.club_forms import LoanEvaluationForm\nfrom customers.club_service import purchase_budget\nfrom django.forms import IntegerField\nassert isinstance(LoanEvaluationForm().fields['proposed_down_payment'], IntegerField)\nazki=LoanProgram.objects.get(provider='azki',term_months=12)\nassert purchase_budget(azki,10_000_000)==72_000_000\nassert any('B3' in item.allowed_guarantor_ranks_for_b for item in LoanProgram.objects.filter(provider='wiki_pay'))\nCustomerCase.objects.values_list('contract_number','guarantor_name','guarantor_credit_rank').first()\nClubAccount.objects.values_list('contract_number','delivery_type','club_fee').first()\nClubPayment.objects.values_list('payment_type','amount','status').first()\nLoanEvaluation.objects.values_list('requested_credit','proposed_down_payment','status').first()\nTask.objects.filter(source_type__in=('club','club_payment')).first()\nget_template('customers/_club_tab.html')\nget_template('customers/_case_tab.html')\ntry:\n    ClubReceiptStorage().url('private')\nexcept ValueError:\n    pass\nelse:\n    raise AssertionError('Club receipts must not have public URLs')\nprint('CLUB WORKFLOW V57 SMOKE CHECK PASSED')\n")
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V57 installed, migrations/checks passed, Passenger restart requested.')
            say('Free-form down payment and explicit rejection reasons are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v57_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
