"""Self-contained cPanel updater V59: layout regression hotfix.
Requires the V58 application source. Place beside manage.py and run with the app Python.
It verifies hashes, backs up source and SQLite, runs checks, and restarts Passenger.
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
eNqlVNtu2zgQ/RVVQYEWkLykRJG6YPsjWSPgZWgToUiDlGJnjfz7UraVTdIUW2BfJHE4M0dnLuecTzAeLJ8g/mGctLNKHw8aQAkuHx9ms9lPo837c+6tyvu8
k3WtqFa4bTAwjUTF65pxypDSTQu0ZlhLRDFRHeEd0xWhGhPQTCgiOkXzIndwTImEoKwTjKQsncQdk40QGinWUaabmmlCBDCJeNNQDg1tOSeCsbbCXaOTs0yJ
QJkp5v39PS6qIr9XfOLl3gTjdmUEC3Iy3m1/bGQYS+slt+VK66wtnHqUoQwj9PXlMw9lYqrKcy+S/XEQ/lRG83fK3AsfFIQyWYYDV2oxdYdThqvDaRh52BnX
t+mckg9X1x6nY/TWqOxOaCU03C7KwJWZY49RCl1Ad8HPTvV3oDXVepDe+tDfYUVAtYP2blr+AfoLlDUOyj2Y3X7q8aYdjnszQRkPXELvfBi5HfwTBG39sTwG
fui5ez7uIcAwwWkquTU714cl/DP611qup9LCE9g/IQQftsXvuh95cKk62/NbalprrKuVmgBc1XItx82oQSpVv/xfGAFihekqghB8hFGQhuq3YeIsJcT4Hgak
TlO/wiDC2oZ9gOFM1wpdYbQBq8pLGWOxubytiVOxUfPBGpl28Hp5fj9HX8x48GHibvqPIfgZ5X5vlAK3LW6cLlevzKKfg4Tt6vQ68847+Bf0bdbX0OCPPyZ1
XjdgGeE3v/mhFb/KkH22eDfut5IZd+FonPb9nsdvn0R8v2zzdciXx0+Bv1SAUvBolv1LGvCXy7fbl+KNGso5Tn6EkOTw6MPjskkPcXq2ED9IIpU1aFCYUQFV
DUBEW2nBWYeTjQgkWooqKTohoVFYdZjSijZNB6SqSdr0V0lUpKVJBUnXYd0hRSmjuK4wQVwlO0aqhRY3LUqCS6FrJeM1iBY1mkoiqqp+J4ltgbsi3xx1yUMw
Twv3pQExO2drn3fBqCFbnuVKexnbeXSxH40b+elbtXS2wBvc6PA9W43txbhY+Dz5IbuoSZkEaIw9uCVn6gWmaUKzW2Ff/gEc0jiJ
"""
PAYLOAD_SHA256 = 'b54be4830d715f87fb1cbb2c1109fee38ad0ea394fc08155e72a6a511815df5c'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v59_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V59 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v59_update.log'
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
            say('Starting layout regression hotfix V59 update.')
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
                    raise RuntimeError('File differs from supported V58 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V58 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V59 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v59-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v59-', dir=path.parent)
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
from crm.private_files import ClubReceiptStorage
from customers.club_models import ClubAccount, ClubPayment, LoanProgram
from customers.club_service import purchase_budget, purchase_difference
from django.template.loader import get_template
assert set(PERMISSIONS) == set(PERMISSION_META)
assert 'purchase_difference' in dict(ClubPayment.TYPES)
azki = LoanProgram.objects.get(provider='azki', term_months=12)
assert purchase_budget(azki, 10_000_000) == 72_000_000
assert purchase_difference(azki, 0, 90_000_000) == 28_000_000
ClubPayment.objects.values_list('payment_type', 'amount', 'status').first()
get_template('customers/_club_tab.html')
get_template('customers/_case_tab.html')
try:
    ClubReceiptStorage().url('private')
except ValueError:
    pass
else:
    raise AssertionError('Club receipts must not have public URLs')
print('CUSTOMER WORKFLOW V59 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V59 installed, migrations/checks passed, Passenger restart requested.')
            say('Filter buttons, search actions and arrival rows are restored without removing inline feedback.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v59_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
