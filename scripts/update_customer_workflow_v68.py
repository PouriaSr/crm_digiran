"""Self-contained cPanel updater V68: connect the call-form address button to real SMS delivery.
Requires the V67 application source. Place beside manage.py and run with the app Python.
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
/wHAgfIC
"""
PAYLOAD_SHA256 = '4c7f00893f78c272a9e674b342d919056fb9dc4582f858dca87bf3114e4d075a'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v68_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V68 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v68_update.log'
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
            say('Starting real address SMS button V68 update.')
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
                    raise RuntimeError('File differs from supported V67 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V67 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V68 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v68-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v68-', dir=path.parent)
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
import inspect
from accounts.permissions import PERMISSIONS
from customers.forms import HubCallForm
from customers.sms import SmsDeliveryResult, send_address_sms
from communications.models import MessageTemplate, TestRun
from django.template.loader import get_template
assert 'communications.send_live' in PERMISSIONS
assert MessageTemplate.objects.filter(channel='sms', name='ارسال آدرس').exists()
assert 'requested_by' in inspect.signature(send_address_sms).parameters
assert 'request_token' in inspect.signature(send_address_sms).parameters
assert bool(SmsDeliveryResult(True, 'ok'))
assert not bool(SmsDeliveryResult(False, 'error'))
assert 'send_address' in HubCallForm().fields
get_template('customers/_call_modal.html')
print('ADDRESS SMS V68 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V68 installed, migrations/checks passed, Passenger restart requested.')
            say('The call-form address button now sends the active SMS template with access control and history.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v68_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
