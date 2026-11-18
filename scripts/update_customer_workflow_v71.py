"""Safe cPanel updater V71: combined customer-status filter.

Requires the V70 application source.  Place this file beside manage.py and run
it with the application's Python interpreter.  The updater verifies the exact
source, backs up SQLite and changed files, applies atomically, checks Django,
and requests a Passenger restart.
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


ROOT = Path(__file__).resolve().parent
FILES = {
    "customers/hub_views.py": {
        "old_sha": "19c51020135b6c283d6184cf4de81045850993368bc548ed04babd3d17128071",
        "new_sha": "a386e38dcbfe8ad133c283d627ee8b23f7d253542a0d7c3a5af0bdecf34d6cf6",
        "old": "ICAgIGlmIHBlcnNvbl9zdGF0dXMgPT0gJ2ludGVydmlld2VyJzoKICAgICAgICBjdXN0b21lcnMgPSBjdXN0b21lcnMuZmlsdGVyKGlzX2ludGVydmlld2VyPVRydWUpCiAgICBlbGlmIHBlcnNvbl9zdGF0dXMgaW4gKCdsZWFkJywgJ3BvdGVudGlhbCcpOgogICAgICAgIGN1c3RvbWVycyA9IGN1c3RvbWVycy5maWx0ZXIoaXNfaW50ZXJ2aWV3ZXI9RmFsc2UsIHN0YWdlPXBlcnNvbl9zdGF0dXMpCg==",
        "new": "ICAgIGlmIHBlcnNvbl9zdGF0dXMgPT0gJ2ludGVydmlld2VyJzoKICAgICAgICBjdXN0b21lcnMgPSBjdXN0b21lcnMuZmlsdGVyKGlzX2ludGVydmlld2VyPVRydWUpCiAgICBlbGlmIHBlcnNvbl9zdGF0dXMgPT0gJ2N1c3RvbWVycyc6CiAgICAgICAgIyBBIHNpbmdsZSBmaWx0ZXIgb3B0aW9uIGZvciBhbGwgYWN0dWFsIGN1c3RvbWVyIHJlY29yZHMuICBLZWVwCiAgICAgICAgIyBpbnRlcnZpZXdlcnMgb3V0IHdoaWxlIHNob3dpbmcgYm90aCBsZWFkIGFuZCBwb3RlbnRpYWwgc3RhZ2VzLgogICAgICAgIGN1c3RvbWVycyA9IGN1c3RvbWVycy5maWx0ZXIoCiAgICAgICAgICAgIGlzX2ludGVydmlld2VyPUZhbHNlLAogICAgICAgICAgICBzdGFnZV9faW49KCdsZWFkJywgJ3BvdGVudGlhbCcpLAogICAgICAgICkKICAgIGVsaWYgcGVyc29uX3N0YXR1cyBpbiAoJ2xlYWQnLCAncG90ZW50aWFsJyk6CiAgICAgICAgY3VzdG9tZXJzID0gY3VzdG9tZXJzLmZpbHRlcihpc19pbnRlcnZpZXdlcj1GYWxzZSwgc3RhZ2U9cGVyc29uX3N0YXR1cykK",
    },
    "templates/customers/hub_table_partial.html": {
        "old_sha": "8337c9a064e29188d22fabdf9bed0089e14ab9fbf582842f6152bd496ee5e1f4",
        "new_sha": "5a72608fadf679e9e1bb3922fb5e0f9365c2acc91b5c1bdc367ef3bec0a249e5",
        "old": "IDxsYWJlbCBkYXRhLWNybS11aT0idWkuY3VzdG9tZXJzLmh1YnRhYmxlcGFydGlhbC5sYWJlbDIiIGRhdGEtY3JtLW9yZGVyPSIyMCI+2YjYtti524zYqjxzZWxlY3QgbmFtZT0icGVyc29uX3N0YXR1cyIgY2xhc3M9InctZnVsbCBtdC0xIGJvcmRlciByb3VuZGVkLWxnIHAtMiBuby1zZWFyY2giPjxvcHRpb24gdmFsdWU9IiI+2YfZhdmHINmI2LbYuduM2KrigIzZh9inPC9vcHRpb24+PG9wdGlvbiB2YWx1ZT0ibGVhZCIgeyUgaWYgdGFibGVfZmlsdGVycy5wZXJzb25fc3RhdHVzID09ICdsZWFkJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2LPYsdmG2K48L29wdGlvbj48b3B0aW9uIHZhbHVlPSJwb3RlbnRpYWwiIHslIGlmIHRhYmxlX2ZpbHRlcnMucGVyc29uX3N0YXR1cyA9PSAncG90ZW50aWFsJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2KjYp9mE2YLZiNmHPC9vcHRpb24+eyUgaWYgJ2N1c3RvbWVycy5jYW5kaWRhdGVfdmlldycgaW4gdXNlcl9wZXJtaXNzaW9ucyAlfTxvcHRpb24gdmFsdWU9ImludGVydmlld2VyIiB7JSBpZiB0YWJsZV9maWx0ZXJzLnBlcnNvbl9zdGF0dXMgPT0gJ2ludGVydmlld2VyJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2YXYtdin2K3YqNmH4oCM2qnZhtmG2K/Zhzwvb3B0aW9uPnslIGVuZGlmICV9PC9zZWxlY3Q+PC9sYWJlbD4K",
        "new": "IDxsYWJlbCBkYXRhLWNybS11aT0idWkuY3VzdG9tZXJzLmh1YnRhYmxlcGFydGlhbC5sYWJlbDIiIGRhdGEtY3JtLW9yZGVyPSIyMCI+2YjYtti524zYqjxzZWxlY3QgbmFtZT0icGVyc29uX3N0YXR1cyIgY2xhc3M9InctZnVsbCBtdC0xIGJvcmRlciByb3VuZGVkLWxnIHAtMiBuby1zZWFyY2giPjxvcHRpb24gdmFsdWU9IiI+2YfZhdmHINmI2LbYuduM2KrigIzZh9inPC9vcHRpb24+PG9wdGlvbiB2YWx1ZT0iY3VzdG9tZXJzIiB7JSBpZiB0YWJsZV9maWx0ZXJzLnBlcnNvbl9zdGF0dXMgPT0gJ2N1c3RvbWVycycgJX1zZWxlY3RlZHslIGVuZGlmICV9PtmF2LTYqtix24zYp9mGICjYs9ix2YbYriDZiCDYqNin2YTZgtmI2YcpPC9vcHRpb24+PG9wdGlvbiB2YWx1ZT0ibGVhZCIgeyUgaWYgdGFibGVfZmlsdGVycy5wZXJzb25fc3RhdHVzID09ICdsZWFkJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2LPYsdmG2K48L29wdGlvbj48b3B0aW9uIHZhbHVlPSJwb3RlbnRpYWwiIHslIGlmIHRhYmxlX2ZpbHRlcnMucGVyc29uX3N0YXR1cyA9PSAncG90ZW50aWFsJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2KjYp9mE2YLZiNmHPC9vcHRpb24+eyUgaWYgJ2N1c3RvbWVycy5jYW5kaWRhdGVfdmlldycgaW4gdXNlcl9wZXJtaXNzaW9ucyAlfTxvcHRpb24gdmFsdWU9ImludGVydmlld2VyIiB7JSBpZiB0YWJsZV9maWx0ZXJzLnBlcnNvbl9zdGF0dXMgPT0gJ2ludGVydmlld2VyJyAlfXNlbGVjdGVkeyUgZW5kaWYgJX0+2YXYtdin2K3YqNmH4oCM2qnZhtmG2K/Zhzwvb3B0aW9uPnslIGVuZGlmICV9PC9zZWxlY3Q+PC9sYWJlbD4K",
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if not (ROOT / "manage.py").is_file():
        raise RuntimeError("Place this script beside manage.py.")
    os.chdir(ROOT)
    lock_path = ROOT / ".workflow_v71_update.lock"
    lock = open(lock_path, "a", encoding="utf-8")
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("Another V71 update is already running.")

    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    log_path = logs / "workflow_v71_update.log"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as log:
        def say(message):
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()

        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "crm.settings"

        def run(*args):
            result = subprocess.run(
                [sys.executable, *args], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
            if result.returncode:
                raise RuntimeError("Command failed: " + " ".join(args[:3]))

        try:
            say("Starting combined customer-status filter V71 update.")
            updates = {}
            for name, spec in FILES.items():
                path = ROOT / name
                if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                    raise RuntimeError("Unsafe file path: " + name)
                original = path.read_bytes().replace(b"\r\n", b"\n")
                current_sha = digest(original)
                if current_sha == spec["new_sha"]:
                    continue
                if current_sha != spec["old_sha"]:
                    raise RuntimeError(
                        "File differs from supported V70 source; no files changed: " + name
                    )
                old = base64.b64decode(spec["old"], validate=True)
                new = base64.b64decode(spec["new"], validate=True)
                if original.count(old) != 1:
                    raise RuntimeError("Expected patch location was not unique: " + name)
                changed = original.replace(old, new, 1)
                if digest(changed) != spec["new_sha"]:
                    raise RuntimeError("Patch verification failed: " + name)
                if name.endswith(".py"):
                    compile(changed, name, "exec")
                updates[name] = changed
            say("Verified V70 source. Files to update: " + str(len(updates)))

            info = subprocess.run(
                [sys.executable, "-c", (
                    "import json; from django.conf import settings; "
                    "d=settings.DATABASES['default']; "
                    "print(json.dumps([d['ENGINE'],str(d['NAME'])]))"
                )],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            if info.returncode:
                log.write(info.stderr)
                raise RuntimeError("Cannot load Django settings; no files changed.")
            engine, database_name = json.loads(info.stdout)
            if engine != "django.db.backends.sqlite3":
                raise RuntimeError("V71 installer currently requires SQLite; no files changed.")
            database = Path(database_name)
            if not database.is_absolute():
                database = ROOT / database
            if not database.is_file() or database.is_symlink():
                raise RuntimeError("SQLite database not found; no files changed.")

            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = ROOT / "backups" / ("workflow-v71-" + stamp)
            backup.mkdir(parents=True, mode=0o700)
            backup.chmod(0o700)
            for name in updates:
                source = ROOT / name
                saved = backup / "files" / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, saved)
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as source:
                with sqlite3.connect(backup / "database.sqlite3") as target:
                    source.backup(target)
                    if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise RuntimeError("Database backup verification failed.")
            (backup / "database.sqlite3").chmod(0o600)
            say("Backup created: " + str(backup))

            for name, content in updates.items():
                path = ROOT / name
                mode = path.stat().st_mode & 0o777
                fd, temporary = tempfile.mkstemp(prefix=".workflow-v71-", dir=path.parent)
                try:
                    with os.fdopen(fd, "wb") as file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                    os.chmod(temporary, mode)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)

            run("manage.py", "check")
            run("manage.py", "migrate", "--check")
            smoke = """import django
django.setup()
from pathlib import Path
from django.template.loader import get_template
view = Path('customers/hub_views.py').read_text(encoding='utf-8')
template = Path('templates/customers/hub_table_partial.html').read_text(encoding='utf-8')
assert "person_status == 'customers'" in view
assert "stage__in=('lead', 'potential')" in view
assert 'value="customers"' in template
assert 'مشتریان (سرنخ و بالقوه)' in template
get_template('customers/hub_table_partial.html')
print('COMBINED CUSTOMER STATUS FILTER V71 SMOKE CHECK PASSED')
"""
            run("-c", smoke)
            restart = ROOT / "tmp"
            restart.mkdir(exist_ok=True)
            (restart / "restart.txt").touch()
            say("SUCCESS: V71 installed, checks passed, Passenger restart requested.")
            say("The Customers status option now combines lead and potential records.")
            say("Log: " + str(log_path))
        except Exception as error:
            say("FAILED: " + str(error))
            say("See logs/workflow_v71_update.log. Backup is preserved; database is not auto-restored.")
            raise SystemExit(1)


if __name__ == "__main__":
    main()
