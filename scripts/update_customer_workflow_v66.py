"""Self-contained cPanel updater V66: secure MelliPayamak simple-send configuration and message templates.
Requires the V65 application source. Place beside manage.py and run with the app Python.
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
ebJ+
"""
PAYLOAD_SHA256 = 'add1869bb322787a92cc81c2af1a49ba7e263f6a9a79b8c75f1b75a60d527e61'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v66_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V66 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v66_update.log'
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
            say('Starting secure MelliPayamak simple-send and message templates V66 update.')
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
                    raise RuntimeError('File differs from supported V65 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V65 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V66 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v66-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v66-', dir=path.parent)
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
from communications.forms import ConfigurationForm, SimulationForm
from communications.models import ChannelConfiguration, MessageTemplate
from communications.services import MELLIPAYAMAK_SIMPLE_ENV, VARIABLES, render_message
from django.template.loader import get_template
assert MELLIPAYAMAK_SIMPLE_ENV == 'MELLIPAYAMAK_SIMPLE_API_URL'
assert {'customer_name','customer_mobile','company_name','expert_name','task_title','contract_number','amount','due_date','address','date','time'} <= set(VARIABLES)
assert MessageTemplate.objects.filter(channel='sms', name='ارسال آدرس', body__contains='{address}').exists()
config = ChannelConfiguration.objects.filter(channel='sms').first()
if config and config.provider == 'melipayamak':
    assert config.credential_env == MELLIPAYAMAK_SIMPLE_ENV
    assert config.connection == {'api_mode': 'console_simple'}
assert 'sample_address' in SimulationForm(channel='sms').fields
assert render_message('سلام {customer_name}؛ {address}', {'customer_name':'آزمایش','address':'تهران'}) == 'سلام آزمایش؛ تهران'
get_template('communications/center.html')
print('MESSAGING V66 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V66 installed, migrations/checks passed, Passenger restart requested.')
            say('Secure MelliPayamak simple-send, template tags, and address template are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v66_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
