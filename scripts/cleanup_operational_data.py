"""Delete CRM operational/test data while preserving users, roles and settings.

Safety rules:
* Put this file beside ``manage.py`` before running it on cPanel.
* Change CONFIRM_OPERATIONAL_PURGE to the exact confirmation phrase below.
* Only SQLite is accepted; a verified database backup is created first.
* Users, groups, permissions, role profiles, permission overrides, employees,
  interface settings, messaging configuration/templates and loan-plan settings
  are deliberately preserved.

Uploaded files are not physically removed.  Their database records are removed,
but the files remain available to an administrator for disaster recovery.
"""

from __future__ import annotations

import datetime
import fcntl
import os
from pathlib import Path
import shutil
import sqlite3
import sys


CONFIRM_OPERATIONAL_PURGE = "CHANGE_ME"
REQUIRED_CONFIRMATION = "DELETE_OPERATIONAL_DATA_KEEP_USERS_AND_ROLES"

ROOT = Path(__file__).resolve().parent
if not (ROOT / "manage.py").is_file():
    # The repository copy lives in scripts/, while the deployable copy is put
    # beside manage.py.  Supporting both makes local verification possible.
    candidate = ROOT.parent
    if (candidate / "manage.py").is_file():
        ROOT = candidate


def fail(message: str) -> "None":
    print("FAILED: " + message, flush=True)
    raise SystemExit(1)


def sqlite_backup(database: Path, destination: Path) -> None:
    database = database.resolve()
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(destination) as target:
            source.backup(target)
            result = target.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                fail("Database backup verification failed: " + str(result))
    destination.chmod(0o600)


def main() -> None:
    if CONFIRM_OPERATIONAL_PURGE != REQUIRED_CONFIRMATION:
        fail(
            "Confirmation is locked. Edit CONFIRM_OPERATIONAL_PURGE and set it "
            "to " + REQUIRED_CONFIRMATION
        )
    if not (ROOT / "manage.py").is_file():
        fail("Place this script beside manage.py.")

    os.chdir(ROOT)
    lock_path = ROOT / ".operational_data_cleanup.lock"
    lock = open(lock_path, "a", encoding="utf-8")
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fail("Another cleanup process is already running.")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")
    import django

    django.setup()

    from django.apps import apps
    from django.conf import settings
    from django.contrib.auth.models import Group, Permission, User
    from django.db import transaction

    database_config = settings.DATABASES["default"]
    if database_config["ENGINE"] != "django.db.backends.sqlite3":
        fail("This cleanup script only supports SQLite; no rows were deleted.")
    database = Path(database_config["NAME"])
    if not database.is_absolute():
        database = ROOT / database
    if not database.is_file() or database.is_symlink():
        fail("A safe SQLite database file was not found; no rows were deleted.")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_dir = ROOT / "backups" / ("operational-purge-" + stamp)
    backup_dir.mkdir(parents=True, mode=0o700)
    backup_dir.chmod(0o700)
    sqlite_backup(database, backup_dir / "database.sqlite3")
    shutil.copy2(Path(__file__), backup_dir / Path(__file__).name)
    print("Verified backup created: " + str(backup_dir), flush=True)

    def model(label: str):
        resolved = apps.get_model(label)
        if resolved is None:
            fail("Required model is unavailable: " + label)
        return resolved

    # These counts must be identical before and after cleanup.  This is an
    # executable guard against deleting authentication/authorization data.
    preserved_models = [
        User,
        Group,
        Permission,
        model("accounts.UserRoleProfile"),
        model("accounts.UserPermissionOverride"),
        model("accounts.InterfaceComponent"),
        model("accounts.InterfaceChange"),
        model("accounts.SectionSchema"),
        model("accounts.SectionField"),
        model("accounts.SectionColumn"),
        model("accounts.SectionStage"),
        model("accounts.SectionTransition"),
        model("accounts.SectionOption"),
        model("accounts.SectionBehavior"),
        model("hr.Employee"),
        model("communications.ChannelConfiguration"),
        model("communications.MessageTemplate"),
        model("customers.LoanProgram"),
    ]
    preserved_before = {
        item._meta.label: item._base_manager.count() for item in preserved_models
    }

    # Children/protected references are intentionally removed before parents.
    # Audit logs and HR tasks are last because delete signals may write them.
    purge_order = [
        "communications.TestRun",
        "accounts.SectionRecordEvent",
        "accounts.SectionRecord",
        "customers.ClubPayment",
        "customers.ClubAccount",
        "customers.LoanEvaluation",
        "sales.InvoiceLog",
        "sales.InvoiceItem",
        "sales.Invoice",
        "customers.HiringReferral",
        "customers.InterviewSession",
        "customers.HiringApplication",
        "customers.HiringAd",
        "customers.HiringAdSequence",
        "customers.CaseWorkSession",
        "customers.CustomerCase",
        "customers.RecordUpdate",
        "customers.FollowUp",
        "customers.Reception",
        "customers.Visit",
        "customers.CustomerNote",
        "calls.Call",
        "customers.Customer",
        "ads.AdLog",
        "ads.Ad",
        "products.StockMovement",
        "products.Product",
        "products.Category",
        "ads.AdProcess",
        "ads.AdPlatform",
        "ads.AdSource",
        "hr.TaskNotice",
        "hr.TaskReport",
        "hr.TaskEvent",
        "hr.Task",
        "hr.LeaveRequest",
        "hr.Attendance",
        "audit.AuditLog",
    ]

    deleted_summary: list[tuple[str, int]] = []
    try:
        with transaction.atomic():
            for label in purge_order:
                target = model(label)
                before = target._base_manager.count()
                if before:
                    target._base_manager.all().delete()
                after = target._base_manager.count()
                if after:
                    raise RuntimeError(f"{label} still has {after} row(s)")
                deleted_summary.append((label, before))

            preserved_after = {
                item._meta.label: item._base_manager.count()
                for item in preserved_models
            }
            if preserved_after != preserved_before:
                changed = {
                    key: (preserved_before[key], preserved_after[key])
                    for key in preserved_before
                    if preserved_before[key] != preserved_after[key]
                }
                raise RuntimeError("Preserved records changed: " + repr(changed))
    except Exception as error:
        fail("Cleanup rolled back: " + str(error))

    restart_dir = ROOT / "tmp"
    restart_dir.mkdir(exist_ok=True)
    (restart_dir / "restart.txt").touch()

    print("SUCCESS: operational/test data was removed.", flush=True)
    print("Preserved users: " + str(preserved_before["auth.User"]), flush=True)
    print("Preserved groups: " + str(preserved_before["auth.Group"]), flush=True)
    print("Preserved role profiles: " + str(preserved_before["accounts.UserRoleProfile"]), flush=True)
    print("Preserved permission overrides: " + str(preserved_before["accounts.UserPermissionOverride"]), flush=True)
    print("Deleted rows by model:", flush=True)
    for label, count in deleted_summary:
        if count:
            print(f"  {label}: {count}", flush=True)
    print("Backup: " + str(backup_dir), flush=True)
    print("Uploaded files were retained for safe recovery.", flush=True)


if __name__ == "__main__":
    main()
