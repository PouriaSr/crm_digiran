from django.db import migrations


def backfill(apps, schema_editor):
    Reception = apps.get_model('customers', 'Reception')
    ClubAccount = apps.get_model('customers', 'ClubAccount')
    Task = apps.get_model('hr', 'Task')
    for rec in Reception.objects.filter(
        workflow_version=2, person_type='customer', case_result='bought', customer__is_deleted=False,
    ).select_related('customer').iterator():
        account = ClubAccount.objects.filter(reception_id=rec.pk).first()
        Task.objects.update_or_create(
            source_key=f'club:{rec.pk}',
            defaults={
                'title': f'ارزیابی و انتخاب وام و گوشی — {rec.customer.name}'[:200],
                'description': 'ارزیابی وام و گوشی را انجام دهید و پیشنهاد انتخاب‌شده را به قرارداد باشگاه تبدیل کنید.',
                'assigned_user_id': rec.customer.assigned_to_id,
                'source_type': 'club', 'source_id': rec.pk, 'source_customer_id': rec.customer_id,
                'status': 'done' if account else 'pending',
                'completed_at': account.joined_at if account else None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0033_seed_loan_programs'),
        ('hr', '0012_task_queue_activation'),
    ]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
