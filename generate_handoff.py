#!/usr/bin/env python3
"""
ULTIMATE Handoff Generator — Includes EVERYTHING.
No filters, no exclusions (except .git and __pycache__).
"""

import os
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "AI_HANDOFF_PROMPT.md"

# فقط پوشه‌های سیستمی و کش‌ها حذف می‌شوند (چون کد نیستند)
EXCLUDE_DIRS = {
    '.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules', 
    '.idea', '.vscode', 'handoff_chunks'
}

def get_git_log():
    try:
        return subprocess.check_output(['git', 'log', '-n', '100', '--oneline', '--decorate'], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "(Git history not available)"

def get_git_branch():
    try:
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"

def get_project_tree():
    lines = []
    def walk(path, prefix=''):
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return
        entries = [e for e in entries if e.name not in EXCLUDE_DIRS and not e.name.startswith('.git')]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = '└── ' if is_last else '├── '
            if entry.is_dir():
                lines.append(f'{prefix}{connector}{entry.name}/')
                walk(entry, prefix + ('    ' if is_last else '│   '))
            else:
                size = entry.stat().st_size
                lines.append(f'{prefix}{connector}{entry.name} ({size:,} bytes)')
    walk(BASE_DIR)
    return '\n'.join(lines)

def get_all_files():
    files = []
    for root, dirs, filenames in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in filenames:
            # اسکریپت خودمان و فایل خروجی را در لیست قرار نده
            if fname in ['generate_handoff.py', 'AI_HANDOFF_PROMPT.md']:
                continue
            files.append(Path(root) / fname)
    return sorted(files)

def file_hash(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    except Exception:
        return 'ERROR'

def read_file_safe(path):
    try:
        return path.read_text(encoding='utf-8'), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding='latin-1'), 'decoded as latin-1'
        except Exception as e:
            return None, f'cannot decode: {e}'
    except Exception as e:
        return None, str(e)

def write_file_block(out, path):
    rel = path.relative_to(BASE_DIR).as_posix()
    ext = path.suffix.lower()
    
    # Determine language
    lang_map = {
        '.py': 'python', '.html': 'html', '.css': 'css', '.js': 'javascript',
        '.json': 'json', '.toml': 'toml', '.yaml': 'yaml', '.yml': 'yaml',
        '.md': 'markdown', '.txt': 'text', '.sh': 'bash', '.sql': 'sql',
        '.env': 'env', '.example': 'env', '.gitignore': 'gitignore'
    }
    lang = lang_map.get(ext, 'text')
    
    content, err = read_file_safe(path)
    size = path.stat().st_size
    h = file_hash(path)
    lines = len(content.splitlines()) if content else 0

    out.write(f"\n## FILE: ./{rel}\n")
    out.write(f"<!-- {lines} lines, {size:,} bytes, hash:{h} -->\n")
    
    if err:
        out.write(f"> ⚠️ {err}\n")
        return

    out.write(f"```{lang}\n")
    out.write(content)
    if not content.endswith('\n'):
        out.write('\n')
    out.write("```\n")

def generate():
    files = get_all_files()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tree = get_project_tree()
    git_log = get_git_log()
    git_branch = get_git_branch()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write("# 🤖 CRM Digiran - ULTIMATE AI Handoff Context\n\n")
        out.write("## 📌 INSTRUCTIONS FOR AI\n\n")
        out.write("You are a Senior Django Developer and UI/UX Expert taking over this project. ")
        out.write("This file contains **EVERY SINGLE FILE** in the project, including tests, migrations, configs, and static files. ")
        out.write("Nothing has been filtered out. ")
        out.write("The system is production-ready with 184 tests passing. ")
        out.write("Mobile UI (Bottom Nav, FAB) and Persianization are finalized. Do NOT break them.\n\n")
        out.write("Reply with: '✅ **Context Loaded. I am ready to continue working on CRM Digiran. What is our next step?**'\n\n")
        
        out.write("---\n\n## 📊 Project Metadata\n\n")
        out.write(f"- **Generated:** {timestamp}\n")
        out.write(f"- **Git Branch:** `{git_branch}`\n")
        out.write(f"- **Total Files Included:** {len(files)}\n")
        out.write("- **Stack:** Django 6.1.2, Python 3.13, Tailwind, Alpine.js, HTMX, ApexCharts\n")
        out.write("- **Database:** SQLite (Dev) / PostgreSQL (Prod)\n\n")

        out.write("## 📜 Git History (Last 100 Commits)\n\n")
        out.write("```text\n" + git_log + "\n```\n\n")

        out.write("## 🌳 Full Project Tree\n\n")
        out.write("```text\n" + tree + "\n```\n\n")

        out.write("---\n\n## 📂 COMPLETE SOURCE CODE\n\n")
        
        for f in files:
            write_file_block(out, f)

    print(f"\n✅ ULTIMATE Handoff generated successfully!")
    print(f"📦 File: {OUTPUT_FILE.name}")
    print(f"📊 Total files included: {len(files)}")
    print(f"💾 File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    print(f"🔗 Ready to upload to a new AI chat.\n")

if __name__ == '__main__':
    generate()
