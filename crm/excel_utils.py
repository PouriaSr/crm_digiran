"""
ابزارهای مشترک ورود داده از Excel — فاز ۷.۸
"""
import io
from datetime import date, datetime

import jdatetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill


# ═══════════════════════════════════════════════════
# خطاها
# ═══════════════════════════════════════════════════
class ExcelImportError(Exception):
    """خطای کلی در خواندن فایل Excel"""
    pass


# ═══════════════════════════════════════════════════
# نرمال‌سازی
# ═══════════════════════════════════════════════════
PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩'


def normalize_digits(value):
    """تبدیل اعداد فارسی/عربی به انگلیسی"""
    if value is None:
        return ''
    s = str(value).strip()
    for i, (p, a) in enumerate(zip(PERSIAN_DIGITS, ARABIC_DIGITS)):
        s = s.replace(p, str(i)).replace(a, str(i))
    return s


def parse_int(value, default=None):
    """تبدیل امن به عدد صحیح"""
    if value is None or value == '':
        return default
    try:
        return int(float(normalize_digits(value).replace(',', '')))
    except (ValueError, TypeError):
        return default


def parse_jalali_date(value):
    """
    تبدیل تاریخ شمسی به میلادی.
    اگر ورودی date/datetime بود، بدون تغییر برمی‌گردونه.
    """
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    s = normalize_digits(value).replace('-', '/').replace('.', '/')
    if ' ' in s:
        s = s.split(' ', 1)[0]

    try:
        y, m, d = map(int, s.split('/'))
        return jdatetime.date(y, m, d).togregorian()
    except (ValueError, AttributeError, TypeError):
        return None


def resolve_choice(raw, choices, default=None):
    """
    تطبیق یک مقدار با choices:
    - اگر key انگلیسی بود → همان
    - اگر display فارسی بود → key
    - وگرنه default
    """
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default

    for k, _ in choices:
        if s == k:
            return k

    for k, v in choices:
        if s == str(v).strip():
            return k

    return default


# ═══════════════════════════════════════════════════
# خواندن فایل Excel
# ═══════════════════════════════════════════════════
def read_xlsx(file_obj, header_map, max_rows=5000):
    """
    file_obj: فایل آپلودشده
    header_map: {نام ستون در اکسل : کلید داخلی}
    max_rows: سقف تعداد ردیف داده

    Returns: (data_rows, missing_headers)
        - data_rows: [{'row_num', '<field>': value, ...}, ...]
        - missing_headers: [str, ...]
    """
    try:
        wb = load_workbook(file_obj, data_only=True, read_only=True)
    except Exception as e:
        raise ExcelImportError(f'فایل Excel خوانده نشد: {e}')

    ws = wb.active
    if ws is None:
        wb.close()
        raise ExcelImportError('فایل هیچ شیت فعالی ندارد.')

    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not all_rows:
        raise ExcelImportError('فایل خالی است.')

    header_row = all_rows[0]
    col_map = {}
    found_keys = set()

    for idx, cell in enumerate(header_row):
        header = str(cell or '').strip()
        if header in header_map:
            col_map[idx] = header_map[header]
            found_keys.add(header_map[header])

    missing = [k for k, v in header_map.items() if v not in found_keys]

    data_rows = []
    for row_num, row in enumerate(all_rows[1:], start=2):
        if len(data_rows) >= max_rows:
            break
        # رد کردن ردیف‌های کاملاً خالی
        if all(c is None or str(c).strip() == '' for c in row):
            continue
        record = {'_row_num': row_num}
        for idx, key in col_map.items():
            record[key] = row[idx] if idx < len(row) else None
        data_rows.append(record)

    return data_rows, missing


# ═══════════════════════════════════════════════════
# ساخت فایل Excel (template)
# ═══════════════════════════════════════════════════

def build_xlsx(headers, sample_row=None, notes=None):
    """
    ساخت فایل xlsx برای دانلود قالب.

    headers: [str, ...]
    sample_row: [value, ...] (اختیاری)
    notes: [str, ...] (اختیاری) — راهنما در پایین فایل
    Returns: bytes
    """
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = 'قالب'
    ws.sheet_view.rightToLeft = True

    header_font = Font(bold=True, color='FFFFFF', size=12)
    header_fill = PatternFill('solid', fgColor='2E86AB')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # ─── ردیف هدرها ───
    ws.append(headers)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
    ws.row_dimensions[1].height = 28

    # ─── ردیف نمونه ───
    if sample_row:
        ws.append(sample_row)
        for cell in ws[2]:
            cell.alignment = Alignment(
                horizontal='right', vertical='center', wrap_text=False,
            )
            cell.font = Font(color='666666', italic=True, size=11)

    # ─── راهنماها (راست‌چین) ───
    if notes:
        ws.append([])  # ردیف خالی جداکننده

        # عنوان راهنما
        guide_header_row = ws.max_row + 1
        ws.append(['راهنمای تکمیل قالب'])
        header_cell = ws.cell(row=guide_header_row, column=1)
        header_cell.font = Font(bold=True, color='2E86AB', size=12)
        header_cell.alignment = Alignment(horizontal='right', vertical='center')

        # محتوای راهنما — هر خط راست‌چین با wrap
        guide_fill = PatternFill('solid', fgColor='F0F7FF')
        thin = Side(style='thin', color='D0E3F1')
        guide_border = Border(left=thin, right=thin, top=thin, bottom=thin)

        for note in notes:
            ws.append([note])
            row = ws.max_row
            cell = ws.cell(row=row, column=1)
            cell.alignment = Alignment(
                horizontal='right',
                vertical='center',
                wrap_text=True,
                indent=0,
            )
            cell.font = Font(size=11, color='1F3A5F')
            cell.fill = guide_fill
            cell.border = guide_border
            ws.row_dimensions[row].height = 22

    # ─── عرض ستون‌ها ───
    for col_idx in range(1, len(headers) + 1):
        letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[letter].width = 22

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()