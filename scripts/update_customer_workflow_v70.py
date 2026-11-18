"""Self-contained cPanel updater V70: system-settings card layout, full-width address action, and call-save fix.
Requires the V69 application source. Place beside manage.py and run with the app Python.
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
eNqtWM1y28gRfhWELpdyIMTBAAMMKFqXPIbtYs0viRUIoDCgJZaiqo1rLfugN9hTLrHXlY1Ka1cc5+BDngK0b/sk6QH4A1KSs3EiWyA409PTv19367wn5qbK
Z6o0g+mcj58l6tQcFove8LyXp7I37PmMa09j5MVaRShkKPQREoEOMInikBNFiYyQ9KX24kBqxQPBtCSaeIIoz5O9fi9Tp8DIiwXxEDDyCQ8Fpr4MPRoIHUhF
PRQQSlAc+35IuSABVRIFnHHg60UepijygJGSSWV6w8ePAz/uBwHq95zVj2Bp6jxy/gAfhzn/TonKHIpSsUr9/knWe/r0ot+r1KxIYcEMmBD5PKvMIMkqVWom
1NioqkqyiTmcVrN0qzwOCVdBzCXC3GMxQUqEmlI/JHGMEMUYcaE0x7EvIh1xpYWMQ+lzLgX2udoqDyp5PgtJgKlUHqIqoF7o40DEWAVRFGNGIkZjQiSlPFAB
iT0hvZDzOAh8H5Gu8qQfgeKjqWJSlY5ImTGPnvQMd6eqzJ/0jkcyedY8unsniThRJewuX9TXX67qG/h96yxfOfWH+qZ+Xf/85Wo0aA5OveP67fKy/seXK6B9
DVT1OyB+B4svRgPYHRXH9Zv6b/V7Z/li+QpOX1vq+saxjJzlJyC+hpfPPy0vm9cfneWf6hvgdQUvy5dA9a69GpYsZzj4Gjj8FZ4v4BRceQO8G2Zwzzv4/ovl
czgaFMcrGfeUY6JK8sxY3Vl3nVeZ0364RZnMWLl40nOmpdKwff7QmZepc7AOhqGpyrmo5qUat4Fz4Dy8AI5Al2QinUu1pR2M+TxJwfrjRORZEzMHzmlSTR37
/dFBkc6NPb4yE6hmTX49GrDjEZ9XVZ451aJQIEX7DaTalRoWJKuYlTqr3KpMJhNwdXeJlRNVAf2DdeS6Ip8VeaZAvJYGZP98CTb91LH6aNBeuLbjoA2iY5sj
/cce7nu+Da098xrV2NedlIlcWUQ7BxvgOATr8PGMZWwCRksyZ27AMoUqZ4kx1i9giV2/rBmmSXayVnVlUdhjpZi6CaRruyHAF5O8XMBRyO7bDtzIMWzkKMp8
UrKZWblvZAqWde+2HoL1Xy/fjQZ2r6WAZ1Xm2eRW6Nvs+PnX76/Agq+/QAC/slEKJ1vqkZmBTDan3sD6D/U/Icbh5XkTtR/sl5v6bf1m+XLLATY+2jUb5hAU
VzYLru2Xzz81OfGq/nv9sUnOW3c/B7I3yx/aFHu/vLTr9fUq7bppvU49SJlWwK6qXWPkhbKxxsqEudNESpXBOuSBshb6/uP6GMQtWFtlEvz+8AJedV46Kyda
h69ex4KV8v/n7fPzNePDdbqtd52Li9+UyavzBxtGJ2rx9bj4hnTfF9IuWiPcFV4dnVLGVQqK7AfTHWpLZUSZFI25mwMt4VdFnRtIx66szcItYZvVPWn/lwix
kWG5WXhpUQXjPt6gSiIt2/shq4txDGB4B/OSKrWY2Ski9xaqVRls7xPlDILPVG6pzDytzPqaNHmm1msbnfnEPZ1CPDo8L219LcGuUkkXn6VO/gzahTQ/XVnC
XlIxnqrNYWAGChnLt904dfUcOpNKnVWumTUHLOR2bzO2KXEJajZLS7DZLVzfVuzLpjJCFfml/vNoUE3voFkXZACQS4CQj/eQweYLiyX1+/v4bAzaEgysRING
ZqDmuVwcr9K/SVnI/a0Prd+rbUPS2s+tGr3k3j2dfLCM7ksGRyYlnEmrslMieZqLk5VJG9sFCDmzyvUcDhFz4jZVYsPZZvw2Z0AXeYc4a+I1pl1cOP/64GxY
JJkcN9EHG231a9bbymPV3smaRjKezpUbIutVy6p+Bz1Q09jYPqvJmQ6i/gepVGZjSf5xoUyWDw+A00dbbfrLT20NWF4e7Ak2ZdlEyVuSdSx3ZtpPNuPgpKgR
tCsklJ116+XU76HFe/mbxQb0vw+Ztw237WYPth6ymLxhk2RQKpSrU3W2n4XpxCnO3MApFq7v7Bt6+cpWwHV8s5WzbQhboWdFtWhDtJU5T60+cF3QubpwactW
KCtqN8pIayObhX/50pTtD009fg79FSTMD1DUb7bdL6TR+6YAd0XYwmObSvBpPbuD5KsXQPKCTZKMNWjdgfHCovhu0q16uTXk7g47nBm1N9X4MfYjjmWMOQs4
PFhAaaw5ZwpzSkQoqK8EwjT2QyRDH+Y+pUNNCAlC4nvhZqrBMLeEMP1I7GMUaB5GkfYZI4RrYAxDm4KRBslYRDQgEaWMRoJHXhjEBA4FfneqiWPSj+NwO9LZ
n1WruY6fw7bJHNsG09zdaoJ9D9gcmB7aUfZ+GrMwTabkmU4m0Crc17i2NSyO476HUNDv7Zt3Oz6P7Qw6nuWSpXv2jmLGQu0JFlPfpwpFJGQeDhFRYBnCmNYK
USkEhwE4xFR4MEcTn/hMYmJnxo29fSpDKWOFcaAxuIspIcNYhTRWkQ8TNczNURxHWGAUIR1zmDl9gRDypAoZ9XZH6D7p9x5Ymd1GZrfM88p53BT6Bo0Bcbht
wxqSzOaBrQJQt5/0np7LxIABFkObo0f24QJSt+A5hMyaz7KjCSuGHi3Ojgom7bEhDoqz3yUQuGXFsuriwS3G5zChQcgP0S2qroSQQo/snyoypaQZ6zyFgjwv
np6zNJlkTSdpGrFcA0NStWXVCrQjw1GDM1OVTKbV0DuMv3KbgeQdgyJQ4c1d6p+WwN0+jrpytCiyWjIq1bY3VZWYHp0mspoOIaYe7kuIdyRs8W/oFWeOydNE
Og8UVlSj1YZbguXmptFrY2gv3GFx26pHnImTSYOpwweaaqbFxbeGwjHAzvnmZnqHi7+BZ3FHKHyrs44tzA91UkIDmGvXDt7nsyRbcwqs5awLh54D/8AhHd8c
fQfpnegFdKrgyKxaOfS/uxpKC9STKfTb5/fe09ZiGybrmNnVll7cRvZtpZjlPEnVOGPPkklTMMZ21tr/Y5YQhPixCGQE+CABZZAvuSZYiohpqaEmAFAJHnCO
fEJ9rWOKEA8xw1ABQryFocADjOcewYLpAODd83DA/djnIaXwP5AIiShQUDqQh0IJMBYhDlhGPaIh2oId2AdcbVH14t/Xlcxb
"""
PAYLOAD_SHA256 = '58ef81cdcdc5e8ab0ca159d8779f50dec43bf0099ec4d96f487eeddc84faf80f'
ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if not (ROOT / 'manage.py').is_file():
        raise RuntimeError('Place this script beside manage.py.')
    os.chdir(ROOT)
    lock_path = ROOT / '.workflow_v70_update.lock'
    lock = open(lock_path, 'a')
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Another V70 update is already running.')
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    log_path = logs / 'workflow_v70_update.log'
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
            say('Starting system-settings layout and full-width address action V70 update.')
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
                    raise RuntimeError('File differs from supported V69 source; no files changed: ' + name)
                lines = old.decode('utf-8').splitlines(keepends=True) if old is not None else []
                for start, end, replacement in reversed(spec['edits']):
                    lines[start:end] = replacement.splitlines(keepends=True)
                new = ''.join(lines).encode('utf-8')
                if sha(new) != spec['new']:
                    raise RuntimeError('Patch verification failed: ' + name)
                if name.endswith('.py'):
                    compile(new, name, 'exec')
                updates[name] = new
            say('Verified V69 source. Files to update: ' + str(len(updates)))
            info = subprocess.run([sys.executable, '-c',
                'import json; from django.conf import settings; d=settings.DATABASES["default"]; print(json.dumps([d["ENGINE"],str(d["NAME"])]))'],
                cwd=ROOT, env=env, capture_output=True, text=True)
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError('Cannot load Django settings; no files changed.')
            engine, database_name = json.loads(info.stdout)
            if engine != 'django.db.backends.sqlite3':
                raise RuntimeError('V70 installer currently requires SQLite; no files changed.')
            db = Path(database_name)
            if not db.is_absolute(): db = ROOT / db
            if not db.is_file():
                raise RuntimeError('SQLite database not found; no files changed.')
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = ROOT / 'backups' / ('workflow-v70-' + stamp)
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
                fd, temporary = tempfile.mkstemp(prefix='.workflow-v70-', dir=path.parent)
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
get_template('customers/_quick_call_modal.html')
get_template('customers/club_program_settings.html')
from pathlib import Path
quick = Path('templates/customers/_quick_call_modal.html').read_text(encoding='utf-8')
plans = Path('templates/customers/club_program_settings.html').read_text(encoding='utf-8')
base = Path('templates/base.html').read_text(encoding='utf-8')
settings_page = Path('templates/accounts/interface_settings.html').read_text(encoding='utf-8')
call_modal = Path('templates/customers/_call_modal.html').read_text(encoding='utf-8')
hub_source = Path('customers/hub_views.py').read_text(encoding='utf-8')
assert 'qc-send-address-row' in quick and quick.index('qc-send-address-row') < quick.index('qc-notes')
assert 'data-open-new-program' in plans and 'data-new-program-modal' in plans
assert plans.index('loan-list-count') < plans.index('data-open-new-program')
assert 'data-category=' in settings_page and 'customers:club_programs' in settings_page
assert 'customers:club_programs' not in base
assert 'flex:1 1 100%;width:100%;justify-content:center' in call_modal
assert 'call = Call.objects.create(' in hub_source
print('SYSTEM SETTINGS LAYOUT AND CALL ADDRESS V70 SMOKE CHECK PASSED')
"""
            run('-c', smoke)
            restart = ROOT / 'tmp'; restart.mkdir(exist_ok=True)
            (restart / 'restart.txt').touch()
            say('SUCCESS: V70 installed, migrations/checks passed, Passenger restart requested.')
            say('Loan plans now live in All Sections, sidebar shortcut is removed, and address action is full width.')
            say('Log: ' + str(log_path))
        except Exception as error:
            say('FAILED: ' + str(error))
            say('See logs/workflow_v70_update.log. Backup is preserved; database is not auto-restored.')
            raise SystemExit(1)

if __name__ == '__main__':
    main()
