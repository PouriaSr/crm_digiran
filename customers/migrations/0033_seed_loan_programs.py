from django.db import migrations


ALL_TO_C3 = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
A_TO_C1 = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1']
A_TO_B2 = ['A1', 'A2', 'A3', 'B1', 'B2']
A_TO_B3 = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']


PROGRAMS = [
    ('azki', 12, 100_000_000, 9_400_000, 85_000_000, 62_000_000, 0, ALL_TO_C3, [], 'چک', 'نوع شغل محدودیتی ندارد'),
    ('azki', 18, 100_000_000, 6_600_000, 80_500_000, 58_000_000, 0, ALL_TO_C3, [], 'چک', 'نوع شغل محدودیتی ندارد'),
    ('gsm', 12, 100_000_000, 9_400_000, 80_000_000, 0, 14_300_000, A_TO_B2, [], 'چک', 'نوع شغل محدودیتی ندارد'),
    ('setare_yek', 12, 100_000_000, 9_400_000, 80_000_000, 0, 14_300_000, A_TO_C1, [], 'چک', 'دولتی/خصوصی: فیش حقوقی مهرشده · آزاد: گردش دو ماه آخر حساب'),
    ('setare_yek', 24, 100_000_000, 5_200_000, 80_000_000, 0, 19_000_000, A_TO_C1, [], 'چک', 'دولتی/خصوصی: فیش حقوقی مهرشده · آزاد: گردش دو ماه آخر حساب'),
    ('wiki_pay', 24, 200_000_000, 10_400_000, 115_000_000, 0, 0, A_TO_B3, ALL_TO_C3, 'ضامن واجد رتبه و چک', 'نوع شغل محدودیتی ندارد'),
    ('wiki_pay', 24, 150_000_000, 7_800_000, 85_000_000, 0, 0, A_TO_B3, ALL_TO_C3, 'ضامن واجد رتبه و چک', 'نوع شغل محدودیتی ندارد'),
    ('wiki_pay', 24, 100_000_000, 5_200_000, 57_000_000, 0, 0, A_TO_B3, ALL_TO_C3, 'ضامن واجد رتبه و چک', 'نوع شغل محدودیتی ندارد'),
    ('wiki_pay', 24, 50_000_000, 2_600_000, 28_000_000, 0, 0, A_TO_B3, ALL_TO_C3, 'ضامن واجد رتبه و چک', 'نوع شغل محدودیتی ندارد'),
]


def seed(apps, schema_editor):
    LoanProgram = apps.get_model('customers', 'LoanProgram')
    for order, row in enumerate(PROGRAMS, 1):
        provider, months, credit, monthly, purchase, no_down, down, ranks, guarantor_ranks, guarantee, employment = row
        LoanProgram.objects.update_or_create(
            provider=provider, term_months=months, credit_limit=credit,
            defaults={'monthly_installment': monthly, 'purchase_limit': purchase,
                      'no_down_purchase_limit': no_down, 'down_payment': down,
                      'allowed_customer_ranks': ranks, 'allowed_guarantor_ranks': guarantor_ranks,
                      'guarantee': guarantee, 'employment_note': employment,
                      'is_active': True, 'order': order},
        )
    CustomerCase = apps.get_model('customers', 'CustomerCase')
    Reception = apps.get_model('customers', 'Reception')
    for case in CustomerCase.objects.filter(visit_result='bought', contract_number__isnull=True).iterator():
        case.contract_number = f'DG-LEGACY-{case.pk:08d}'
        case.save(update_fields=['contract_number'])
        latest = Reception.objects.filter(
            customer_id=case.customer_id, workflow_version=2, person_type='customer',
        ).order_by('-created_at', '-pk').first()
        if latest and latest.case_result != 'bought':
            latest.case_result = 'bought'
            latest.save(update_fields=['case_result'])


class Migration(migrations.Migration):
    dependencies = [('customers', '0032_customercase_contract_number_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
