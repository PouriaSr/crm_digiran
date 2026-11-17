from calendar import monthrange
from datetime import date

from django.db.models import Q

from products.models import Product

from .club_models import ClubPayment, LoanProgram


MOBILE_PRODUCTS = (
    Q(category__slug__iexact='mobile') |
    Q(category__name__icontains='موبایل') |
    Q(category__name__icontains='گوشی') |
    Q(name__icontains='موبایل') |
    Q(name__icontains='گوشی')
)


def program_eligibility(program, case):
    """Return (eligible, explanation). Rules are intentionally deterministic."""
    if program.provider in (case.active_loans or []):
        return False, 'این وام در پرونده به‌عنوان وام فعال ثبت شده است.'
    if not case.credit_rank:
        return False, 'رتبه اعتباری مشتری در پرونده ثبت نشده است.'
    if case.credit_rank not in (program.allowed_customer_ranks or []):
        return False, f'رتبه اعتباری {case.credit_rank} برای این طرح مجاز نیست.'
    if program.provider == 'wiki_pay':
        guarantor_ranks = program.allowed_guarantor_ranks or []
        if case.credit_rank.startswith('B') and program.allowed_guarantor_ranks_for_b:
            guarantor_ranks = program.allowed_guarantor_ranks_for_b
        if not case.guarantor_name:
            return False, 'نام ضامن برای ویکی‌پی در پرونده ثبت نشده است.'
        if not case.guarantor_credit_rank:
            return False, 'رتبه اعتباری ضامن برای ویکی‌پی ثبت نشده است.'
        if case.guarantor_credit_rank not in guarantor_ranks:
            return False, f'رتبه ضامن {case.guarantor_credit_rank} با رتبه مشتری {case.credit_rank} برای ویکی‌پی مجاز نیست.'
    if program.provider == 'setare_yek' and case.job not in ('government', 'private', 'freelance'):
        return False, 'نوع شغل برای مدارک مورد قبول ستاره یک مناسب نیست.'
    return True, ''


def purchase_budget(program, proposed_down_payment):
    if program.no_down_purchase_limit:
        return min(program.purchase_limit, program.no_down_purchase_limit + proposed_down_payment)
    return program.purchase_limit


def maximum_purchase_price(program, proposed_down_payment):
    """Main purchase amount available for choosing a phone."""
    return loan_purchase_amount(program, proposed_down_payment) + proposed_down_payment


def loan_purchase_amount(program, proposed_down_payment):
    """Purchase ceiling granted by the selected loan program."""
    return program.purchase_limit


def covered_purchase_amount(program, proposed_down_payment):
    """Amount covered by the usable loan share plus the entered down payment."""
    return loan_purchase_amount(program, proposed_down_payment) + proposed_down_payment


def purchase_difference(program, proposed_down_payment, product_price):
    """Unused part of the main purchase amount after choosing the phone."""
    return max(0, covered_purchase_amount(program, proposed_down_payment) - int(product_price))


def evaluate_case(case, requested_credit, proposed_down_payment):
    programs, rejected = [], []
    candidates = LoanProgram.objects.filter(
        is_active=True, credit_limit=requested_credit, down_payment__lte=proposed_down_payment,
    ).order_by('order', 'term_months', '-purchase_limit')
    for program in candidates:
        accepted, reason = program_eligibility(program, case)
        if accepted:
            programs.append(program)
        else:
            rejected.append({'program': str(program), 'reason': reason})
    max_budget = max((maximum_purchase_price(item, proposed_down_payment) for item in programs), default=0)
    products = list(Product.objects.filter(is_active=True, stock__gt=0, price__lte=max_budget)
                    .filter(MOBILE_PRODUCTS).select_related('category').order_by('-price', 'name')[:20]) if max_budget else []
    return programs, products, rejected


def add_months(value, months):
    index = value.month - 1 + months
    year, month = value.year + index // 12, index % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def create_payment_schedule(account):
    program = account.loan_program
    today = date.today()
    rows = []
    actual_down_payment = account.down_payment_amount
    if actual_down_payment:
        rows.append(ClubPayment(account=account, payment_type='down_payment', amount=actual_down_payment,
                                due_date=today, status='scheduled', created_by=account.selected_by))
    if account.club_fee:
        rows.append(ClubPayment(account=account, payment_type='club_fee', amount=account.club_fee,
                                due_date=today, status='scheduled', created_by=account.selected_by))
    difference = account.purchase_difference_amount
    if difference:
        rows.append(ClubPayment(
            account=account, payment_type='purchase_difference', amount=difference,
            due_date=today, status='scheduled', created_by=account.selected_by,
            notes='رسید یا فاکتور پرداخت مابه‌التفاوت میان مبلغ خرید اصلی و قیمت گوشی را ثبت کنید.',
        ))
    rows.extend(ClubPayment(account=account, payment_type='installment', amount=program.monthly_installment,
                            due_date=add_months(today, number), status='scheduled', created_by=account.selected_by)
                for number in range(1, program.term_months + 1))
    ClubPayment.objects.bulk_create(rows)


def reconcile_payment_schedule(account, actor=None):
    """Refresh future, unreceipted obligations without rewriting financial history."""
    today = date.today()
    editable = account.payments.filter(status__in=('scheduled', 'overdue'), receipt='')

    def sync_single(payment_type, amount, note=''):
        rows = list(editable.filter(payment_type=payment_type).order_by('due_date', 'pk'))
        if not amount:
            for row in rows:
                row.delete()
            return
        row = rows.pop(0) if rows else ClubPayment(account=account, payment_type=payment_type)
        row.amount = amount
        row.due_date = row.due_date or today
        row.status = 'scheduled'
        row.notes = note or row.notes
        row.created_by = row.created_by or actor
        row.save()
        for duplicate in rows:
            duplicate.delete()

    sync_single('down_payment', account.down_payment_amount)
    sync_single('club_fee', account.club_fee)
    sync_single(
        'purchase_difference', account.purchase_difference_amount,
        'رسید یا فاکتور پرداخت مابه‌التفاوت میان مبلغ خرید اصلی و قیمت گوشی را ثبت کنید.',
    )

    locked_count = account.payments.filter(payment_type='installment').exclude(
        status__in=('scheduled', 'overdue'), receipt='',
    ).exclude(status='cancelled').count()
    desired = max(account.loan_program.term_months - locked_count, 0)
    future = list(editable.filter(payment_type='installment').order_by('due_date', 'pk'))
    keep, remove = future[:desired], future[desired:]
    for row in remove:
        row.delete()
    for row in keep:
        changed = []
        if row.amount != account.loan_program.monthly_installment:
            row.amount = account.loan_program.monthly_installment
            changed.append('amount')
        if row.status != 'scheduled':
            row.status = 'scheduled'
            changed.append('status')
        if changed:
            row.save(update_fields=changed + ['updated_at'])
    missing = desired - len(keep)
    if missing:
        last_due = account.payments.filter(payment_type='installment', due_date__isnull=False).order_by('-due_date').values_list('due_date', flat=True).first() or today
        ClubPayment.objects.bulk_create([
            ClubPayment(
                account=account, payment_type='installment',
                amount=account.loan_program.monthly_installment,
                due_date=add_months(last_due, number), status='scheduled', created_by=actor,
            )
            for number in range(1, missing + 1)
        ])
