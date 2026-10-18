import re
from pathlib import Path

def fix_file(path_str, broken_patterns):
    p = Path(path_str)
    if not p.exists():
        return
    c = p.read_text(encoding='utf-8')
    original = c
    
    for pattern in broken_patterns:
        c = re.sub(pattern, '', c, flags=re.DOTALL)
        
    if c != original:
        p.write_text(c, encoding='utf-8')
        print(f"  ✅ Fixed syntax in {path_str}")
    else:
        print(f"  - No syntax errors found in {path_str}")

# 1. calls/forms.py
fix_file('calls/forms.py', [
    # Remove orphaned elif block for call_date
    r'\s*elif not self\.instance\.pk:\s*\n\s*now = timezone\.localtime\(timezone\.now\(\)\)\s*\n\s*j = jdatetime\.datetime\.fromgregorian\(datetime=now\)\s*\n\s*self\.initial\[\'call_date\'\] = j\.strftime\(\'%Y/%m/%d %H:%M\'\)\s*'
])

# 2. sales/forms.py
fix_file('sales/forms.py', [
    # Remove orphaned else block for issue_date
    r'\s*else:\s*\n\s*j = jdatetime\.date\.fromgregorian\(date=timezone\.now\(\)\.date\(\)\)\s*\n\s*self\.initial\[\'issue_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\s*'
])

# 3. hr/forms.py
fix_file('hr/forms.py', [
    # Remove orphaned else for hire_date in EmployeeForm
    r'\s*else:\s*\n\s*self\.fields\[\'user\'\]\.queryset = User\.objects\.filter\(employee_profile__isnull=True\)\s*\n\s*j = jdatetime\.date\.fromgregorian\(date=timezone\.now\(\)\.date\(\)\)\s*\n\s*self\.initial\[\'hire_date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\s*',
    # Remove orphaned else for date in AttendanceForm
    r'\s*else:\s*\n\s*j = jdatetime\.date\.fromgregorian\(date=timezone\.now\(\)\.date\(\)\)\s*\n\s*self\.initial\[\'date\'\] = j\.strftime\(\'%Y/%m/%d\'\)\s*'
])

print("🎉 Syntax check and fix complete.")
