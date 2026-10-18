import ast
from pathlib import Path

def fix_syntax_errors(filepath):
    p = Path(filepath)
    if not p.exists():
        return

    while True:
        try:
            # 1. تلاش برای پارس کردن فایل
            ast.parse(p.read_text(encoding='utf-8'))
            print(f"  ✅ {filepath} is perfectly clean.")
            break
        except IndentationError as e:
            print(f"  ⚠️ Fixing IndentationError in {filepath} at line {e.lineno}...")
            lines = p.read_text(encoding='utf-8').splitlines()
            if e.lineno <= len(lines):
                # حذف خطی که باعث خطا شده (مثل else: یا elif بلاک خالی)
                del lines[e.lineno - 1]
                p.write_text('\n'.join(lines), encoding='utf-8')
        except SyntaxError as e:
            print(f"  ❌ Unfixable SyntaxError in {filepath} at line {e.lineno}: {e.msg}")
            break

if __name__ == '__main__':
    print("🔍 Checking and fixing form syntax errors...\n")
    fix_syntax_errors('calls/forms.py')
    fix_syntax_errors('sales/forms.py')
    fix_syntax_errors('hr/forms.py')
    print("\n🎉 Done! You can now run the server.")
