"""Run beside manage.py. Change only customer-hub column alignment."""
from pathlib import Path
from datetime import datetime
import shutil

root = Path(__file__).resolve().parent
block = '''/* Customer hub column alignment: names right, remaining columns centered. */
.workflow-hub table th,.workflow-hub table td { text-align:center !important; }
.workflow-hub table .hub-name-column { text-align:right !important; }
.wf-summary>.wf-name,.wf-list-head>:first-child { text-align:right; }
.wf-summary>:not(.wf-name),.wf-list-head>:not(:first-child) { text-align:center; }
.wf-summary>.wf-actions { justify-content:center; }
'''
changes = {
    'templates/customers/_workflow_styles.html': [('</style>', block + '</style>')],
    'templates/customers/hub_table_partial.html': [
        ('class="p-3 font-medium text-right">نام مشتری', 'class="p-3 font-medium text-right hub-name-column">نام مشتری'),
        ('<td class="p-3 text-right">', '<td class="p-3 text-right hub-name-column">'),
    ],
    'templates/customers/hub.html': [
        ('class="p-4 font-semibold text-center">مشتری</th>', 'class="p-4 font-semibold text-right hub-name-column">مشتری</th>'),
        ('class="p-4 font-bold text-gray-800 text-center">{{ inv.customer.name }}', 'class="p-4 font-bold text-gray-800 text-right hub-name-column">{{ inv.customer.name }}'),
    ],
}
updates = {}
for name, edits in changes.items():
    path = root / name
    text = path.read_text(encoding='utf-8')
    updated = text
    for old, new in edits:
        if new in updated:
            continue
        if updated.count(old) != 1:
            raise SystemExit('Unsupported template; no files changed: ' + name)
        updated = updated.replace(old, new, 1)
    if updated != text:
        updates[name] = updated
if updates:
    backup = root / 'backups' / ('hub-alignment-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, mode=0o700)
    for name, content in updates.items():
        path = root / name
        saved = backup / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, saved)
        path.write_text(content, encoding='utf-8')
    (root / 'tmp').mkdir(exist_ok=True)
    (root / 'tmp/restart.txt').touch()
print('SUCCESS: names right-aligned; remaining customer-hub columns centered.')
