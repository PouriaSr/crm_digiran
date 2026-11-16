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
    """Maximum phone price that can be offered before the customer-paid difference."""
    return program.credit_limit + proposed_down_payment


def loan_purchase_amount(program, proposed_down_payment):
    """Snapshot-worthy part of the purchase ceiling financed by the loan itself."""
    usable = purchase_budget(program, proposed_down_payment)
    if program.no_down_purchase_limit:
        return max(0, usable - proposed_down_payment)
    return usable


def covered_purchase_amount(program, proposed_down_payment):
    """Amount covered by the usable loan share plus the entered down payment."""
    return loan_purchase_amount(program, proposed_down_payment) + proposed_down_payment


def purchase_difference(program, proposed_down_payment, product_price):
    """Customer-paid part left after the usable lender contribution."""
    return max(0, int(product_price) - covered_purchase_amount(program, proposed_down_payment))


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
            notes='مابه‌التفاوت قیمت گوشی و سهم قابل‌استفاده طرح وام؛ رسید پرداخت را ثبت کنید.',
        ))
    rows.extend(ClubPayment(account=account, payment_type='installment', amount=program.monthly_installment,
                            due_date=add_months(today, number), status='scheduled', created_by=account.selected_by)
                for number in range(1, program.term_months + 1))
    ClubPayment.objects.bulk_create(rows)
