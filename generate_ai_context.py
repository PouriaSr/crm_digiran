#!/usr/bin/env python3
"""
CRM Digiran — AI Full Context Generator
تولید فایل AI_FULL_CONTEXT.md برای پیوست به چت AI.

اجرا:
    python generate_ai_context.py                # همه‌چیز (توصیه‌شده)
    python generate_ai_context.py --no-git       # بدون تاریخچه گیت
    python generate_ai_context.py --no-content   # فقط درخت + متادیتا
    python generate_ai_context.py --max-lines 3000  # سقف خط هر فایل
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "AI_FULL_CONTEXT.md"
MAX_FILE_LINES = 5000
MAX_TOTAL_SIZE_MB = 15


# ═══════════════════════════════════════════════════════════
# تنظیمات
# ═══════════════════════════════════════════════════════════
INCLUDE_EXTENSIONS = {
    ".py", ".html", ".css", ".js", ".md", ".txt",
    ".toml", ".json", ".yml", ".yaml", ".ini",
    ".env.example", ".example", ".xml",
}

INCLUDE_SPECIAL_NAMES = {
    "manage.py", "requirements.txt", "pyproject.toml",
    "Dockerfile", "Procfile", ".env.example",
    "README.md", "passenger_wsgi.py",
    ".gitignore",
}

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__",
    "node_modules", "staticfiles", "media",
    "backups", "logs",
    ".idea", ".vscode",
    ".patch_backup", ".rbac_fix_backup",
    ".mobile_fix_backup", ".mobile_fix_backup_2",
    ".duplicate_fix_backup",
    "migrations/__pycache__",
}

EXCLUDE_FILES = {
    "db.sqlite3", ".DS_Store", "package-lock.json",
    "uv.lock", "poetry.lock",
    "AI_FULL_CONTEXT.md", "AI_HANDOFF_PROMPT.md",
    "generate_ai_context.py", "generate_dump.py",
    "generate_context.py", "measure_queries.py",
    "project_dump.txt", "project_context_for_ai.txt",
    "fix_indentation.py", "fix_bi_typeerror.py",
    "fix_rbac_complete.py", "fix_mobile_tables.py",
    "fix_mobile_css_placement.py", "fix_duplicate_complete.py",
    "apply_patch.py", "fix_font_unification.py",
}

# ═══════════════════════════════════════════════════════════
# ابزارها
# ═══════════════════════════════════════════════════════════
def run_git(args, default=""):
    try:
        out = subprocess.check_output(
            ["git"] + args, cwd=BASE, stderr=subprocess.DEVNULL, text=True,
        )
        return out
    except Exception:
        return default


def get_git_commits(limit=200):
    out = run_git(
        ["log", f"-{limit}", "--pretty=format:%h|%ad|%an|%s", "--date=short"],
    )
    if not out:
        return []
    commits = []
    for line in out.strip().split("\n"):
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0],
                "date": parts[1],
                "author": parts[2],
                "subject": parts[3],
            })
    return commits


def get_git_status():
    return run_git(["status", "--short"]).strip()


def get_git_branch():
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()


def get_git_remote():
    return run_git(["remote", "-v"]).strip()


def get_git_last_commit():
    return run_git(["log", "-1", "--pretty=format:%H|%ad|%s", "--date=iso"]).strip()


def get_git_tags():
    return run_git(["tag", "--sort=-creatordate"]).strip().split("\n") if run_git(["tag"]) else []


def is_git_repo():
    return (BASE / ".git").exists()


# ═══════════════════════════════════════════════════════════
# پیمایش درخت
# ═══════════════════════════════════════════════════════════
def walk_files():
    files = []
    for root, dirs, filenames in os.walk(BASE):
        # حذف دایرکتوری‌های exclud
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIRS
            and not d.startswith(".")
            and not (Path(root) / d).relative_to(BASE).as_posix() in EXCLUDE_DIRS
        ]

        for name in sorted(filenames):
            if name in EXCLUDE_FILES:
                continue
            if name.startswith(".") and name not in INCLUDE_SPECIAL_NAMES:
                continue

            path = Path(root) / name
            rel = path.relative_to(BASE)

            # بررسی پسوند
            ext = path.suffix.lower()
            if ext not in INCLUDE_EXTENSIONS and name not in INCLUDE_SPECIAL_NAMES:
                continue

            # اندازه
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 5 * 1024 * 1024:  # 5MB
                continue

            files.append((rel, path, size))

    files.sort(key=lambda x: str(x[0]))
    return files


def build_tree(files):
    """ساخت درخت ASCII از روی لیست فایل‌ها"""
    tree = {}
    for rel, _, _ in files:
        parts = rel.parts
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    lines = []

    def render(node, prefix=""):
        items = sorted(node.items(), key=lambda kv: (not bool(kv[1]), kv[0]))
        for i, (name, children) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if children else ""
            lines.append(f"{prefix}{connector}{name}{suffix}")
            if children:
                ext = "    " if is_last else "│   "
                render(children, prefix + ext)

    render(tree)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# خواندن محتوا
# ═══════════════════════════════════════════════════════════
def read_file(path, max_lines):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except Exception as e:
            return f"[خطا در خواندن فایل: {e}]"

    lines = text.split("\n")
    if len(lines) > max_lines:
        head = lines[:max_lines]
        return "\n".join(head) + f"\n\n[... {len(lines) - max_lines} خط دیگر حذف شد ...]"
    return text


# ═══════════════════════════════════════════════════════════
# ساخت خروجی
# ═══════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-git", action="store_true", help="بدون تاریخچه گیت")
    ap.add_argument("--no-content", action="store_true", help="بدون محتوای فایل‌ها")
    ap.add_argument("--max-lines", type=int, default=MAX_FILE_LINES)
    args = ap.parse_args()

    print("🔍 در حال پیمایش پروژه...")
    files = walk_files()
    print(f"   {len(files)} فایل پیدا شد.")

    total_size = sum(s for _, _, s in files) / (1024 * 1024)
    print(f"   حجم کل: {total_size:.2f} MB")

    if total_size > MAX_TOTAL_SIZE_MB:
        print(f"⚠️  حجم بیش از {MAX_TOTAL_SIZE_MB}MB — کاهش max-lines توصیه می‌شود.")

    print(f"📝 ساخت {OUTPUT.name}...")

    with open(OUTPUT, "w", encoding="utf-8") as out:
        # ─── هدر ───
        out.write("# 🤖 CRM Digiran — AI Full Context\n\n")
        out.write(f"> **Generated:** `{datetime.now().isoformat(timespec='seconds')}`\n")
        out.write(f"> **Project Root:** `{BASE}`\n\n")

        out.write("## 📌 دستور کار برای AI\n\n")
        out.write("این فایل شامل **کل وضعیت پروژه** است. پس از مطالعه، پاسخ بده با:\n\n")
        out.write("> ✅ **Context Loaded. Ready to continue.**\n\n")
        out.write("سپس منتظر بمان تا کاربر بگوید قدم بعدی چیست.\n\n")

        out.write("### ⚠️ نکات حفظ‌شده (Do NOT break)\n\n")
        out.write("- 📱 **Mobile Bottom Nav + FAB + Mobile Cards**\n")
        out.write("- 🇮🇷 **Persianization** (PersianDigitsMiddleware, ApexCharts wrapper, Vazirmatn)\n")
        out.write("- 🔒 **RBAC** (accounts/permissions.py — single source of truth)\n")
        out.write("- 🌐 **RTL** + `dir=\"rtl\"` on `<html>`\n")
        out.write("- 🎨 **Vazirmatn font** (globally enforced via CSS `!important`)\n")
        out.write("- 🛡 **Soft Delete** (Customer, Product, User)\n")
        out.write("- 🔁 **Real-time duplicate check** (MutationObserver in base.html)\n")
        out.write("- 📊 **Desktop layout finalized** — don't redesign\n\n")

        out.write("---\n\n")

        # ─── 1. خلاصه پروژه ───
        out.write("## 1️⃣ شناسنامه پروژه\n\n")
        out.write("| فیلد | مقدار |\n")
        out.write("|------|-------|\n")
        out.write("| نام | CRM Digiran |\n")
        out.write("| نوع | Persian/RTL CRM |\n")
        out.write("| Backend | Django 6.x (Python 3.13) |\n")
        out.write("| Frontend | Tailwind CDN + Alpine.js + HTMX + ApexCharts |\n")
        out.write("| DB | SQLite (dev) / PostgreSQL (prod) |\n")
        out.write("| Auth | Django Auth + django-otp (2FA) + custom RateLimit |\n")
        out.write("| Test | Django TestCase (~200 tests) |\n\n")

        # ─── 2. وضعیت گیت ───
        if is_git_repo() and not args.no_git:
            out.write("## 2️⃣ وضعیت گیت\n\n")

            branch = get_git_branch()
            out.write(f"**Branch:** `{branch}`\n\n")

            remote = get_git_remote()
            if remote:
                out.write(f"**Remote:**\n```\n{remote}\n```\n\n")

            last = get_git_last_commit()
            if last:
                parts = last.split("|", 2)
                out.write(f"**Last Commit:**\n")
                out.write(f"- Hash: `{parts[0]}`\n")
                out.write(f"- Date: `{parts[1]}`\n")
                out.write(f"- Message: {parts[2]}\n\n")

            tags = get_git_tags()
            if tags and tags[0]:
                out.write(f"**Tags:** {', '.join(f'`{t}`' for t in tags[:10])}\n\n")

            status = get_git_status()
            if status:
                out.write("**Uncommitted changes:**\n```\n")
                out.write(status[:2000])
                if len(status) > 2000:
                    out.write("\n[... truncated ...]")
                out.write("\n```\n\n")
            else:
                out.write("**Working tree:** ✅ clean\n\n")

            # تاریخچه
            commits = get_git_commits(limit=100)
            if commits:
                out.write(f"### تاریخچه (آخرین {len(commits)} کامیت)\n\n")
                out.write("```\n")
                for c in commits:
                    out.write(f"{c['hash']}  {c['date']}  {c['subject']}\n")
                out.write("```\n\n")
        else:
            out.write("## 2️⃣ وضعیت گیت\n\n_گیت ردیابی نشد._\n\n")

        # ─── 3. ساختار پروژه ───
        out.write("## 3️⃣ ساختار درخت پروژه\n\n")
        out.write("```\n")
        out.write(build_tree(files))
        out.write("\n```\n\n")

        out.write(f"**تعداد فایل‌های قابل خواندن:** {len(files)}\n")
        out.write(f"**حجم کل:** {total_size:.2f} MB\n\n")

        # ─── 4. محتوای فایل‌ها ───
        if not args.no_content:
            out.write("---\n\n")
            out.write("## 4️⃣ محتوای فایل‌های سورس\n\n")
            out.write(f"_حداکثر {args.max_lines} خط برای هر فایل_\n\n")

            for rel, path, size in files:
                ext = path.suffix.lower()
                if ext not in INCLUDE_EXTENSIONS and path.name not in INCLUDE_SPECIAL_NAMES:
                    continue

                out.write(f"### `./{rel.as_posix()}`\n\n")

                # تشخیص زبان
                lang_map = {
                    ".py": "python", ".html": "html", ".js": "javascript",
                    ".css": "css", ".json": "json", ".yml": "yaml",
                    ".yaml": "yaml", ".toml": "toml", ".md": "markdown",
                    ".ini": "ini", ".txt": "text", ".xml": "xml",
                }
                lang = lang_map.get(ext, "")
                if path.name == ".env.example":
                    lang = "bash"
                if path.name == ".gitignore":
                    lang = "gitignore"

                content = read_file(path, args.max_lines)
                out.write(f"```{lang}\n")
                out.write(content.rstrip())
                out.write("\n```\n\n")

        # ─── 5. راهنمای ادامه ───
        out.write("---\n\n")
        out.write("## 5️⃣ راهنمای ادامه‌ی کار\n\n")

        out.write("### دستورات کلیدی\n\n")
        out.write("```bash\n")
        out.write("# راه‌اندازی\n")
        out.write("uv sync                       # نصب وابستگی‌ها\n")
        out.write("python manage.py migrate      # ساخت جدول‌ها\n")
        out.write("python manage.py runserver    # اجرا\n\n")
        out.write("# تست\n")
        out.write("python manage.py test                    # همه\n")
        out.write("python manage.py test accounts customers # یک اپ\n\n")
        out.write("# backup\n")
        out.write("python manage.py backup_db\n")
        out.write("```\n\n")

        out.write("### نقش‌ها و دسترسی‌ها\n\n")
        out.write("📁 `accounts/permissions.py` — منبع واحد حقیقت. تغییر نقش‌ها از اینجا.\n\n")

        out.write("### فایل‌های کلیدی برای تغییر\n\n")
        out.write("| هدف | فایل |\n")
        out.write("|-----|-------|\n")
        out.write("| ماتریس دسترسی | `accounts/permissions.py` |\n")
        out.write("| چک لحظه‌ای تکراری | `crm/duplicate_api.py` + `crm/form_mixins.py` + `base.html` JS |\n")
        out.write("| Soft delete | `customers/models.py`, `products/models.py` |\n")
        out.write("| اعداد فارسی | `crm/middleware.py` (PersianDigitsMiddleware) |\n")
        out.write("| نمودارها | `base.html` (ApexCharts wrapper) |\n")
        out.write("| تقویم شمسی | `base.html` (jalalidatepicker) |\n")
        out.write("| نقش‌ها | `accounts/forms.py`, `accounts/views.py` |\n\n")

        out.write("### قواعد پاسخگویی\n\n")
        out.write("1. **همیشه** Persian (fa) پاسخ بده، مگر اینکه کاربر انگلیسی بپرسد.\n")
        out.write("2. کدهای نهایی را **در قالب یک بلوک `bash` با heredoc** بده که کاربر فقط کپی/پیست کند.\n")
        out.write("3. بعد از هر تغییر: **بررسی کن** با `python manage.py check`.\n")
        out.write("4. تست‌های موجود را نشکن.\n")
        out.write("5. **موبایل** را نشکن (Bottom Nav, FAB, Mobile Cards).\n")
        out.write("6. اگر پچ به `base.html` یا `middleware` مربوط شد، **بکاپ بگیر** و بعد patch کن.\n\n")

    print(f"✅ {OUTPUT.name} ساخته شد.")
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"📦 حجم: {size_mb:.2f} MB")
    print(f"📄 تعداد خطوط: {sum(1 for _ in OUTPUT.open(encoding='utf-8')):,}")
    print()
    print("💡 استفاده:")
    print(f"   - فایل `{OUTPUT.name}` را باز کن و کل محتوا را کپی کن")
    print("   - در چت جدید AI پیست کن")
    print("   - AI با پاسخ «✅ Context Loaded» آماده ادامه است.")
    print()
    print("⚠️  اگر فایل بیش از ۱۰ مگابایت شد:")
    print("   python generate_ai_context.py --max-lines 1500 --no-git")
    print()


if __name__ == "__main__":
    main()
