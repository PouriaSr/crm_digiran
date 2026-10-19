import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "AI_HANDOFF_PROMPT.md"

EXCLUDE_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'backups', 'staticfiles', 'media', '.idea', '.vscode', 'logs'}
EXCLUDE_EXTS = {'.pyc', '.pyo', '.pyd', '.sqlite3', '.gz', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.sqlite'}
ALLOW_EXT = {'.py', '.html', '.txt', '.md', '.toml', '.json', '.css', '.js', '.example'}

def get_git_log():
    try:
        log = subprocess.check_output(['git', 'log', '-n', '20', '--oneline'], text=True)
        return log
    except Exception:
        return "Git log not available.\n"

def generate():
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write("# 🤖 CRM Digiran - AI Handoff Context\n\n")
        out.write("## 📌 INSTRUCTIONS FOR AI\n")
        out.write("You are a Senior Django Developer and UI/UX Expert taking over this project. ")
        out.write("Read this entire file to understand the project state. ")
        out.write("The system is production-ready with 184 tests passing. ")
        out.write("Do NOT break the mobile responsiveness (Bottom Nav, FAB, Hero Cards). ")
        out.write("Do NOT break the Persianization (ApexCharts wrapper, PersianDigitsMiddleware). ")
        out.write("Desktop layout is finalized.\n\n")
        out.write("When you have read and understood the context, reply with: ")
        out.write("'✅ **Context Loaded. I am ready to continue working on CRM Digiran. What is our next step?**'\n\n")
        
        out.write("---\n\n## 🏗️ PROJECT OVERVIEW\n")
        out.write("- **Name:** CRM Digiran (Persian/RTL CRM)\n")
        out.write("- **Stack:** Django 6.1.2, Python 3.13, Tailwind CSS (via CDN), Alpine.js, HTMX\n")
        out.write("- **Database:** SQLite (Dev) / Ready for PostgreSQL (Prod)\n")
        out.write("- **Key Features:** RBAC, 2FA, Excel Import/Export, BI Charts, Soft Delete, Audit Trail, Persian Numerals\n\n")
        
        out.write("## 📜 RECENT GIT HISTORY\n```text\n")
        out.write(get_git_log())
        out.write("```\n\n")
        
        out.write("## 📂 PROJECT FILES (Source Code)\n")
        out.write("Below are the contents of the project files. Pay special attention to `crm/middleware.py`, `templates/base.html`, and the `models.py`/`views.py` files.\n\n")

        for root, dirs, files in os.walk(BASE_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                name = file_path.name.lower()
                
                if ext in EXCLUDE_EXTS:
                    continue
                if ext not in ALLOW_EXT and not name.endswith('.env.example'):
                    continue

                rel_path = file_path.relative_to(BASE_DIR)
                
                out.write(f"### FILE: `./{rel_path}`\n")
                out.write("```" + ("html" if ext == ".html" else "python" if ext == ".py" else "text"))
                out.write(f"\n")
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    out.write(content)
                    if not content.endswith('\n'):
                        out.write('\n')
                except UnicodeDecodeError:
                    out.write("[BINARY FILE SKIPPED]\n")
                except Exception as e:
                    out.write(f"[ERROR READING FILE: {e}]\n")
                
                out.write("```\n\n")

    print(f"✅ Handoff file generated successfully: {OUTPUT_FILE.name}")
    print(f"📦 File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

if __name__ == '__main__':
    generate()
