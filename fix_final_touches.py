#!/usr/bin/env python3
"""
Fix Final Touches:
1. Remove auto-date fields from forms (call_date, issue_date, hire_date, attendance date).
2. Persianize all placeholders in .py and .html files.

Usage:
    python fix_final_touches.py
"""

import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

def fa_digits(text):
    return text.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

def persianize_placeholders(content):
    # HTML style: placeholder="..."
    content = re.sub(
        r'(placeholder\s*=\s*["\'])(.*?)(["\'])',
        lambda m: m.group(1) + fa_digits(m.group(2)) + m.group(3),
        content
    )
    # Python style: 'placeholder': '...'
    content = re.sub(
        r'([\'"]placeholder[\'"]\s*:\s*[\'"])(.*?)([\'"])',
        lambda m: m.group(1) + fa_digits(m.group(2)) + m.group(3),
        content
    )
    return content

def process_forms():
    # 1. calls/forms.py
    p = BASE / 'calls' / 'forms.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        # Remove field definition
        c = re.sub(r'\n    call_date = forms\.CharField\([\s\S]*?\n    \)', '', c)
        # Remove clean method
        c = re.sub(r'def clean_call_date\(self\):[\s\S]*?raise forms\.ValidationError\(\'تاریخ یا ساعت معتبر نیست\'\)\n', '', c)
        # Remove from fields list
        c = c.replace("'call_date', ", "")
        # Remove init logic
        c = re.sub(r'# ═══ مقدار اولیه برای تاریخ تماس ═══\n(?:.*\n)*?.*?self.initial\[\'call_date\'\] = j.strftime\(\'%Y/%m/%d %H:%M\'\)\n', '', c)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ calls/forms.py updated")

    # 2. sales/forms.py
    p = BASE / 'sales' / 'forms.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = re.sub(r'\n    issue_date = forms\.CharField\([\s\S]*?\n    \)', '', c)
        c = re.sub(r'def clean_issue_date\(self\):[\s\S]*?raise forms\.ValidationError\(\'تاریخ معتبر نیست\'\)\n', '', c)
        c = c.replace("'issue_date', ", "")
        c = re.sub(r'if self\.instance and self\.instance\.pk and self\.instance\.issue_date:\n(?:.*\n)*?.*?self\.initial\[\'issue_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n(?:.*\n)*?.*?self\.initial\[\'issue_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n', '', c)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ sales/forms.py updated")

    # 3. hr/forms.py
    p = BASE / 'hr' / 'forms.py'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        # EmployeeForm
        c = re.sub(r'\n    hire_date = forms\.CharField\([\s\S]*?\n    \)', '', c)
        c = re.sub(r'def clean_hire_date\(self\):[\s\S]*?return result or timezone\.now\(\)\.date\(\)\n', '', c)
        c = c.replace("'hire_date', ", "")
        c = re.sub(r'if self\.instance\.hire_date:\n(?:.*\n)*?.*?self\.initial\[\'hire_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n', '', c)
        c = re.sub(r'j = jdatetime\.date\.fromgregorian\(date=timezone\.now\(\)\.date\(\)\)\n            self\.initial\[\'hire_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n', '', c)
        
        # AttendanceForm
        c = re.sub(r'\n    date = forms\.CharField\([\s\S]*?\n    \)', '', c)
        c = re.sub(r'def clean_date\(self\):[\s\S]*?raise forms\.ValidationError\(\'تاریخ معتبر نیست\'\)\n', '', c)
        c = c.replace("'date', ", "")
        c = re.sub(r'if self\.instance and self\.instance\.pk and self\.instance\.date:\n(?:.*\n)*?.*?self\.initial\[\'date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n(?:.*\n)*?.*?self\.initial\[\'date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\n', '', c)
        
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ hr/forms.py updated")

def process_templates():
    # calls/form.html
    p = BASE / 'templates' / 'calls' / 'form.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = re.sub(r'<div[^>]*>\s*<label[^>]*>تاریخ تماس</label>\s*\{\{ form\.call_date \}\}\s*</div>', '', c, flags=re.DOTALL)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ calls/form.html updated")

    # sales/form.html
    p = BASE / 'templates' / 'sales' / 'form.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = re.sub(r'<div[^>]*>\s*<label[^>]*>تاریخ صدور</label>\s*\{\{ form\.issue_date \}\}\s*</div>', '', c, flags=re.DOTALL)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ sales/form.html updated")

    # hr/employee_form.html
    p = BASE / 'templates' / 'hr' / 'employee_form.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = re.sub(r'<div[^>]*><label[^>]*>تاریخ استخدام</label>\s*\{\{ form\.hire_date \}\}\s*</div>', '', c, flags=re.DOTALL)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ hr/employee_form.html updated")

    # hr/attendance_form.html
    p = BASE / 'templates' / 'hr' / 'attendance_form.html'
    if p.exists():
        c = p.read_text(encoding='utf-8')
        c = re.sub(r'<div[^>]*>\s*<label[^>]*>تاریخ.*?</label>\s*\{\{ form\.date \}\}\s*</div>', '', c, flags=re.DOTALL)
        p.write_text(persianize_placeholders(c), encoding='utf-8')
        print("  ✅ hr/attendance_form.html updated")

def process_all_placeholders():
    for root, dirs, files in os.walk(BASE):
        if any(x in root for x in ['.git', '.venv', 'venv', '__pycache__', 'backups', 'staticfiles', 'media']):
            continue
        for f in files:
            if f.endswith('.py') or f.endswith('.html'):
                p = Path(root) / f
                # Skip our own script
                if p.name == 'fix_final_touches.py':
                    continue
                try:
                    c = p.read_text(encoding='utf-8')
                    new_c = persianize_placeholders(c)
                    if c != new_c:
                        p.write_text(new_c, encoding='utf-8')
                        print(f"  ✅ Placeholders updated: {p.relative_to(BASE)}")
                except Exception as e:
                    print(f"  ⚠️ Error on {p.name}: {e}")

if __name__ == '__main__':
    print("🚀 Applying Final Requirements...\n")
    print("1️⃣ Removing auto-date fields from forms...")
    process_forms()
    process_templates()
    
    print("\n2️⃣ Persianizing all placeholders system-wide...")
    process_all_placeholders()
    
    print("\n🎉 Done! All forms auto-populate dates, and all placeholders use Persian digits.")
