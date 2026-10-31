"""
ابزارهای مشترک ورود داده از Excel — فاز ۷.۸
"""
import io
from datetime import date, datetime

import jdatetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from .numerals import ascii_digits, normalize_input


# ═══════════════════════════════════════════════════
# خطاها
# ═══════════════════════════════════════════════════
class ExcelImportError(Exception):
    """خطای کلی در خواندن فایل Excel"""
    pass


# ═══════════════════════════════════════════════════
# نرمال‌سازی
# ═══════════════════════════════════════════════════
def normalize_digits(value):
    """تبدیل اعداد فارسی/عربی به انگلیسی"""
    if value is None:
        return ''
    return ascii_digits(value).strip()


def parse_int(value, default=None):
    """تبدیل امن به عدد صحیح"""
    if value is None or value == '':
        return default
    try:
        return int(float(normalize_input(value)))
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
        if all(c is None or str(c).strip() == '' for c in row):
            continue
        record = {'_row_num': row_num}
        for idx, key in col_map.items():
            record[key] = row[idx] if idx < len(row) else None
        data_rows.append(record)

    return data_rows, missing


# ═══════════════════════════════════════════════════
# ساخت فایل Excel (template) — نسخه‌ی ۲
# ═══════════════════════════════════════════════════
# استایل‌های مشترک (توی ماژول)
_HEADER_FONT = Font(bold=True, color='FFFFFF', size=12)
_HEADER_FILL = PatternFill('solid', fgColor='2E86AB')
_CENTER = Alignment(horizontal='center', vertical='center', wrap_text=True)
_RIGHT = Alignment(horizontal='right', vertical='center', wrap_text=True)
_THIN = Side(style='thin', color='D0E3F1')
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _style_header(ws, row_num, n_cols):
    """اعمال استایل روی ردیف هدر"""
    for col_idx in range(1, n_cols + 1):
        cell = ws.cell(row=row_num, column=col_idx)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER
    ws.row_dimensions[row_num].height = 28


def _write_guide_section(ws, title, lines):
    """نوشتن یک بخش راهنما با عنوان"""
    # ردیف خالی جداکننده
    ws.append([])

    # عنوان بخش
    ws.append([title])
    title_row = ws.max_row
    title_cell = ws.cell(row=title_row, column=1)
    title_cell.font = Font(bold=True, color='FFFFFF', size=12)
    title_cell.fill = PatternFill('solid', fgColor='4A90C2')
    title_cell.alignment = _CENTER
    title_cell.border = _BORDER
    ws.row_dimensions[title_row].height = 26

    # خطوط راهنما
    for line in lines:
        ws.append([line])
        row = ws.max_row
        cell = ws.cell(row=row, column=1)
        cell.alignment = _RIGHT
        cell.font = Font(size=11, color='1F3A5F')
        cell.fill = PatternFill('solid', fgColor='F0F7FF')
        cell.border = _BORDER
        # ارتفاع بر اساس طول متن
        ws.row_dimensions[row].height = 22


def build_xlsx(headers, sample_row=None, notes=None, choices_sections=None):
    """
    ساخت فایل xlsx برای دانلود قالب — نسخه‌ی ۲ با شیت راهنما.

    headers:         [str, ...]  — ستون‌های شیت اصلی
    sample_row:      [value, ...] — ردیف نمونه (اختیاری)
    notes:           [str, ...]  — راهنمای کوتاه در پایین شیت اصلی
    choices_sections: [           — بخش‌های راهنمای دقیق در شیت «راهنما»
        {
            'title': 'وضعیت مشتری',
            'column': 'وضعیت',
            'items': [
                ('بالقوه (لید)', 'مشتری علاقه‌مند که هنوز خرید نکرده'),
                ...
            ]
        },
        ...
    ]
    Returns: bytes
    """
    wb = Workbook()

    # ═══════════════════════════════════════════════════════
    # شیت اصلی: قالب
    # ═══════════════════════════════════════════════════════
    ws = wb.active
    ws.title = 'قالب'
    ws.sheet_view.rightToLeft = True

    ws.append(headers)
    _style_header(ws, 1, len(headers))

    if sample_row:
        ws.append(sample_row)
        for cell in ws[2]:
            cell.alignment = Alignment(horizontal='right', vertical='center')
            cell.font = Font(color='666666', italic=True, size=11)

    if notes:
        ws.append([])
        for note in notes:
            ws.append([note])
            row = ws.max_row
            cell = ws.cell(row=row, column=1)
            cell.alignment = _RIGHT
            cell.font = Font(size=11, color='1F3A5F')
            cell.fill = PatternFill('solid', fgColor='F0F7FF')
            cell.border = _BORDER
            ws.row_dimensions[row].height = 22

    for col_idx in range(1, len(headers) + 1):
        letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[letter].width = 22

    # ═══════════════════════════════════════════════════════
    # شیت راهنما (اگه choices_sections داده شده)
    # ═══════════════════════════════════════════════════════
    if choices_sections:
        wg = wb.create_sheet('راهنما')
        wg.sheet_view.rightToLeft = True

        # عنوان بزرگ
        wg.append(['راهنمای مقادیر مجاز'])
        row = wg.max_row
        cell = wg.cell(row=row, column=1)
        cell.font = Font(bold=True, size=16, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='2E86AB')
        cell.alignment = _CENTER
        wg.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        wg.row_dimensions[row].height = 36

        # زیرنویس
        wg.append(['این فایل شامل مقادیر مجاز برای پر کردن دقیق قالب است.'])
        row = wg.max_row
        wg.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        cell = wg.cell(row=row, column=1)
        cell.font = Font(size=11, italic=True, color='666666')
        cell.alignment = _CENTER
        wg.row_dimensions[row].height = 20

        wg.append([])

        # هر بخش
        for section in choices_sections:
            title = section.get('title', '')
            column = section.get('column', '')
            items = section.get('items', [])

            # عنوان بخش
            wg.append([f'■ {title}'])
            row = wg.max_row
            wg.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
            cell = wg.cell(row=row, column=1)
            cell.font = Font(bold=True, color='FFFFFF', size=12)
            cell.fill = PatternFill('solid', fgColor='4A90C2')
            cell.alignment = _RIGHT
            cell.border = _BORDER
            wg.row_dimensions[row].height = 26

            # هدر جدول
            wg.append(['مقدار (کپی کنید)', 'توضیح', 'ستون مربوطه'])
            row = wg.max_row
            for col_idx in (1, 2, 3):
                c = wg.cell(row=row, column=col_idx)
                c.font = Font(bold=True, color='2E86AB', size=11)
                c.fill = PatternFill('solid', fgColor='E6F2FA')
                c.alignment = _CENTER
                c.border = _BORDER
            wg.row_dimensions[row].height = 22

            # اقلام
            for value, desc in items:
                wg.append([value, desc, column])
                row = wg.max_row
                # ستون مقدار (کپی‌کردنی — با فونت monospace)
                c1 = wg.cell(row=row, column=1)
                c1.font = Font(size=11, bold=True, color='1F3A5F')
                c1.alignment = _RIGHT
                c1.fill = PatternFill('solid', fgColor='FFF9E6')
                c1.border = _BORDER
                # توضیح
                c2 = wg.cell(row=row, column=2)
                c2.font = Font(size=11, color='333333')
                c2.alignment = _RIGHT
                c2.border = _BORDER
                # ستون
                c3 = wg.cell(row=row, column=3)
                c3.font = Font(size=11, color='666666')
                c3.alignment = _CENTER
                c3.border = _BORDER
                wg.row_dimensions[row].height = 22

            wg.append([])

        # تنظیم عرض ستون‌ها
        wg.column_dimensions['A'].width = 30
        wg.column_dimensions['B'].width = 55
        wg.column_dimensions['C'].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
