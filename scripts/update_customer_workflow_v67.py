"""Self-contained cPanel updater V67: show safe MelliPayamak provider failure details.
Requires the V66 application source. Place beside manage.py and run with the app Python.
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
eNqNks9q20AQxl9lUA+yiZGl1T9LUHoovfVQWnqyTFlpV43AkYRWcgjG0ECc5OA36AO4CbSucaH00ufYtW99ko4cB0N66bAszOzHb2Y+dqolxdlZk2cJrbMi
F33Bq0mWcGGUF1o41Yox00LNiimPbeIPSGoGqcVTNnA8N4hNJ3BMxyKx5RAauwmxPSe2OfF4QCw7GXCPWpQyS+tpOT9HEPG81HQtJ3EJMRPTtmNKE8+0KUpN
x3VpQngaEG55vh8w201iSmhixY7LmJ/aDEGcZbXQwuHQ93t4NDhEWRWTjPHqg6hp3Qh4DhU3RBN3Kj2KxIneAx3wEnXVKenFuKDM+Mjrjv4g17tQVKDr3a6B
iqzsdKNcG/WGA7M3sI5NnsGbQxs4tMkENIKnzRhSBIimLIuq7kHc1JDzSas7Lc7h/dvXom1Ac2jyuGhyxhnOJ0q0nBtR/h9LnNZ1KV6E/X4UvdtvM1TX8odc
quvdAuRX+V1dAuarEb49wXSHIXHM0bEN4zXNxkhPdVC/dwukzEFu5FrdYrIJYfqEMNMhS/+Zjo8FR8+O3IpmWHm06GWR5zxpv9WrqiqqzlHXhq7m6mq3+PNp
8TjB9g4XwKWWcqNuQM3lL3kvv8g1YGWN0y3VFbS5ut6usLBqd8f7M8hv8ieoy73ovq2pG7mA7Qqx64cU1G0LxEdA1XKPaeVo3faudVCuDB1ODsYcB93/gtFs
9heWuTzv
"""
PAYLOAD_SHA256 = 'cdd4b046cd0a661f8b8759eabaffb9bcbbfd30fc07f3cb38a0ac6ee01328b345'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v67_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V67 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v67_update.log'
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
            say('Starting safe MelliPayamak provider failure details V67 update.')
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
                    raise RuntimeError('File differs from supported V66 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V66 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V67 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v67-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v67-', dir=path.parent)
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
print('MESSAGING V67 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V67 installed, migrations/checks passed, Passenger restart requested.')
            say('Safe MelliPayamak provider failure details are active.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v67_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
