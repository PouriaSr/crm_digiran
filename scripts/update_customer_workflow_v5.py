"""Self-contained cPanel updater for known previous CRM versions.
Copy this file beside manage.py and execute it with the app's Python.
It verifies source hashes, backs up code and SQLite, runs migrations/checks,
and requests a Passenger restart. It never restores the database automatically.
The compressed JSON contains verified text edits only; no downloaded code is executed.
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
VX4ElOSVzF6a1ppKzf3/C5Qd8rA=
"""
PAYLOAD_SHA256 = '95cee1a23e522473563601baa6cd8e65af685d616bb14c02c0e92253ac57254f'
ROOT = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock = open(ROOT / '.workflow_v5_update.lock', 'a')
    os.chmod(ROOT / '.workflow_v5_update.lock', 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v5_update.log'
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as log:
        def say(message):
            print(message, flush=True)
            log.write(message + '\n')
            log.flush()

        def run(*args):
            log.flush()
            result = subprocess.run(
                [sys.executable, *args], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            if result.returncode:
                raise RuntimeError('Command failed: ' + ' '.join(args[:3]))

        try:
            say('Starting customer workflow V5 update.')
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
                if digest == spec['old']:
                    edits = spec['edits']
                elif (digest or 'missing') in spec.get('variants', {}):
                    edits = spec['variants'][digest or 'missing']
                else:
                    raise RuntimeError('File differs from the supported version; no application files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(edits):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified all source files. Files to update: ' + str(len(updates)))
            env = os.environ.copy()
            env['DJANGO_SETTINGS_MODULE'] = 'crm.settings'
            info = subprocess.run(
                [sys.executable, '-c',
                 'import json; from django.conf import settings; '
                 'd=settings.DATABASES["default"]; '
                 'print(json.dumps({"engine":d["ENGINE"],"name":str(d["NAME"])}))'],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load existing Django settings; no application files changed.')
            database = json.loads(info.stdout)
            if database['engine'] != 'django.db.backends.sqlite3':
                raise RuntimeError('This installer requires the current SQLite development database; no application files changed.')
            db = Path(database['name'])
            if not db.is_absolute():
                db = ROOT / db
            if not db.is_file():
                raise RuntimeError('Existing SQLite database not found; no application files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v5-' + stamp)
            backup.mkdir(parents=True, mode=0o700)
            backup.chmod(0o700)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v5-', dir=path.parent)
                try:
                    with os.fdopen(fd, 'wb') as file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                    os.chmod(temporary, mode)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            say('Application files updated. Applying migrations...')
            run('manage.py', 'migrate', '--noinput')
            run('manage.py', 'check')
            run('manage.py', 'migrate', '--check')
            smoke = '''
import django
django.setup()
from calls.models import Call
from customers.forms import HubCallForm
from django.conf import settings
from django.test import Client
Call.objects.values_list('requested_condition', 'send_address', 'follow_up_time').first()
from customers.models import FollowUp
FollowUp.objects.values_list('due_date', 'due_time').first()
from django.template.loader import get_template
for template in ('customers/hub.html', 'customers/detail.html', 'customers/_call_history_items.html'):
    get_template(template)
data = {'mobile':'09123456789', 'name':'Smoke test', 'notes':'Test', 'call_type':'incoming'}
f = HubCallForm(data)
assert f.is_valid(), f.errors
assert not HubCallForm(dict(data, mobile='123')).is_valid()
assert not HubCallForm(dict(data, name='')).is_valid()
f = HubCallForm(dict(data, customer_analysis='potential', follow_up_date='1405/09/15'))
assert not f.is_valid() and 'follow_up_time' in f.errors
f = HubCallForm(dict(data, customer_analysis='potential', follow_up_date='1405/09/15', follow_up_time='10:30'))
assert f.is_valid(), f.errors
host = next((h for h in settings.ALLOWED_HOSTS if h != '*' and not h.startswith('.')), 'localhost')
r = Client().get('/accounts/login/', secure=True, HTTP_HOST=host)
assert r.status_code == 200, r.status_code
assert b'csrfmiddlewaretoken' in r.content and b'password' in r.content
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from customers.hub_views import customer_hub
admin = User.objects.filter(is_active=True, is_superuser=True).first()
if admin:
    request = RequestFactory().get('/customers/hub/', secure=True, HTTP_HOST=host)
    request.user = admin
    request.session = {}
    request._messages = FallbackStorage(request)
    response = customer_hub(request)
    assert response.status_code == 200
print('SMOKE CHECK PASSED: login, workflow, database fields, templates and customer hub.')
'''
            run('-c', smoke)
            restart = ROOT / 'tmp'
            restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: files updated, migrations applied, checks passed, Passenger restart requested.')
            say('SMS remains TEST ONLY; no real SMS is sent.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v5_update.log. Backups are preserved; the database is NOT automatically restored.')
            raise SystemExit(1)


if __name__ == '__main__':
    main()
