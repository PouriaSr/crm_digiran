import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "project_context_for_ai.txt"

EXCLUDE_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', 'backups', 'staticfiles', 'media', '.idea', '.vscode'}
EXCLUDE_EXTS = {'.pyc', '.pyo', '.pyd', '.sqlite3', '.gz', '.png', '.jpg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot'}
ALLOW_EXT = {'.py', '.html', '.txt', '.md', '.toml', '.json', '.css', '.js', '.example'}

def get_git_log():
    try:
        log = subprocess.check_output(['git', 'log', '-n', '15', '--oneline'], text=True)
        return log
    except Exception:
        return "Git log not available.\n"

def generate():
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write("============================================================\n")
        out.write("📌 GIT COMMIT HISTORY (آخرین ۱۵ کامیت)\n")
        out.write("============================================================\n")
        out.write(get_git_log())
        out.write("\n\n============================================================\n")
        out.write("📌 PROJECT FILES (ساختار و محتوای فایل‌های کلیدی)\n")
        out.write("============================================================\n")

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
                
                out.write(f"\n==================================================\n")
                out.write(f"FILE: ./{rel_path}\n")
                out.write(f"==================================================\n")
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    out.write(content + "\n")
                except UnicodeDecodeError:
                    out.write("[BINARY FILE SKIPPED]\n")
                except Exception as e:
                    out.write(f"[ERROR READING FILE: {e}]\n")

    print(f"✅ Context generated successfully: {OUTPUT_FILE.name}")
    print(f"📦 File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")

if __name__ == '__main__':
    generate()
