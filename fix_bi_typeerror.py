#!/usr/bin/env python3
"""
Fix TypeError in dashboard/views.py caused by Invoice.issue_date being DateTimeField.
Subtracting datetime from date is invalid; we need to extract date from both.
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent
VIEWS_FILE = BASE / 'dashboard' / 'views.py'

def fix():
    if not VIEWS_FILE.exists():
        print("❌ dashboard/views.py not found.")
        return

    content = VIEWS_FILE.read_text(encoding='utf-8')
    original = content

    # The problematic line:
    # delta = (first_inv - c.first_contact_date.date()).days
    # OR
    # delta = (first_inv.date() - c.first_contact_date.date()).days

    # Let's fix it by ensuring first_inv uses .date()
    content = content.replace(
        "delta = (first_inv - c.first_contact_date.date()).days",
        "delta = (first_inv.date() - c.first_contact_date.date()).days"
    )

    if content != original:
        VIEWS_FILE.write_text(content, encoding='utf-8')
        print("✅ dashboard/views.py patched successfully.")
    else:
        print("ℹ️ No changes made (pattern not found or already patched).")

    # Check for other potential date math issues in the same file
    # Look for _get_dashboard_data or _get_bi_data where dates are subtracted
    print("\n🔍 Scanning for other potential date arithmetic...")
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if ('issue_date' in line or 'hire_date' in line) and ('-' in line or '+' in line) and 'Sum' not in line and '=' in line and 'models' not in line:
            if '.date()' not in line and 'datetime' not in line:
                print(f"  ⚠️ Line {i} may need review: {line.strip()}")

if __name__ == '__main__':
    print("🔧 Applying BI TypeError fix...\n")
    fix()
    print("\n🎉 Done! Restart the server and check /bi/.")
