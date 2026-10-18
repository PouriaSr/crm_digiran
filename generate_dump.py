import os
import subprocess

# پوشه‌هایی که نباید داخل فایل متنی کپی شوند (چون حجیم یا غیرضروری هستند)
IGNORE_DIRS = {
    '.git', '.venv', '__pycache__', 'node_modules', 
    'staticfiles', 'media', 'backups', 'logs', 
    '.idea', '.vscode', 'env', 'venv'
}

# فایل‌های حساس یا دیتابیس که نباید کپی شوند
IGNORE_FILES = {
    '.env', 'db.sqlite3', '.DS_Store', 'project_dump.txt', 
    'generate_dump.py', 'package-lock.json'
}

# فقط پسوندهای متنی که نیاز داریم
ALLOWED_EXTENSIONS = {
    '.py', '.html', '.css', '.js', '.md', '.txt', 
    '.json', '.yml', '.yaml', '.toml', '.ini', '.example', '.xml'
}

def generate_dump(output_file='project_dump.txt'):
    print(f"⏳ در حال ساخت فایل {output_file} ...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # ─── ۱. نوشتن تاریخچه گیت (کامیت‌ها) ───
        f.write("=" * 60 + "\n")
        f.write("📌 GIT COMMIT HISTORY (تاریخچه تغییرات)\n")
        f.write("=" * 60 + "\n")
        try:
            # گرفتن ۵۰ کامیت آخر به صورت خلاصه
            git_log = subprocess.check_output(
                ['git', 'log', '--oneline', '--decorate', '-n', '50'], 
                text=True, encoding='utf-8'
            )
            f.write(git_log + "\n")
        except Exception as e:
            f.write("⚠️ تاریخچه گیت یافت نشد یا پوشه گیت نیست.\n")

        f.write("\n\n" + "=" * 60 + "\n")
        f.write("📌 PROJECT FILES (فایل‌های پروژه)\n")
        f.write("=" * 60 + "\n")

        # ─── ۲. پیمایش درخت پروژه و خواندن فایل‌ها ───
        for root, dirs, files in os.walk('.'):
            # حذف پوشه‌های غیرضروری از لیست جستجو
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            # مرتب‌سازی فایل‌ها برای خوانایی بهتر
            files.sort()

            for file in files:
                if file in IGNORE_FILES:
                    continue
                
                ext = os.path.splitext(file)[1].lower()
                if ext not in ALLOWED_EXTENSIONS and file not in ['manage.py', 'Dockerfile', 'requirements.txt']:
                    continue

                filepath = os.path.join(root, file)
                
                f.write(f"\n{'=' * 50}\n")
                f.write(f"FILE: {filepath}\n")
                f.write(f"{'=' * 50}\n")
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        f.write(infile.read())
                        f.write("\n")
                except Exception as e:
                    f.write(f"[خطا در خواندن فایل: {e}]\n")

    print(f"✅ فایل {output_file} با موفقیت ساخته شد!")
    print(f"📦 حجم فایل: {os.path.getsize(output_file) / 1024:.1f} کیلوبایت")
    print("\n👉 حالا می‌توانید محتوای این فایل را کپی کرده و در چت برای من بفرستید.")

if __name__ == '__main__':
    generate_dump()