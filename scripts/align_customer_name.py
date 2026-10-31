"""Run beside manage.py to right-align only the customer-name column."""
from pathlib import Path
from datetime import datetime
import shutil

root = Path(__file__).resolve().parent
path = root / 'templates/customers/hub_table_partial.html'
changes = [
    ('<th class="p-3 font-medium">نام مشتری</th>', '<th class="p-3 font-medium text-right">نام مشتری</th>'),
    ('<td class="p-3 text-center">\n                        <div class="flex items-center justify-center gap-2">',
     '<td class="p-3 text-right">\n                        <div class="flex items-center justify-start gap-2">'),
]
text = path.read_text(encoding='utf-8')
updated = text
for old, new in changes:
    if new in updated:
        continue
    if updated.count(old) != 1:
        raise SystemExit('Unsupported template; no files changed.')
    updated = updated.replace(old, new, 1)
if updated != text:
    backup = root / 'backups' / ('name-alignment-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(path, backup / path.name)
    path.write_text(updated, encoding='utf-8')
    (root / 'tmp').mkdir(exist_ok=True)
    (root / 'tmp/restart.txt').touch()
print('SUCCESS: customer-name column is right-aligned.')
