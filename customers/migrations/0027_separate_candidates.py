from django.db import migrations, models


def align_candidates(apps, schema_editor):
    alias=schema_editor.connection.alias
    Customer=apps.get_model('customers','Customer');Reception=apps.get_model('customers','Reception')
    Task=apps.get_model('hr','Task')
    ids=Reception.objects.using(alias).filter(person_type='interviewer').values('customer_id')
    Customer.objects.using(alias).filter(pk__in=ids).update(is_interviewer=True)
    people=Customer.objects.using(alias).filter(is_interviewer=True)
    people.update(needs_followup=False)
    # Preserve incompatible unfinished customer visits as legacy records without fabricating completion times.
    Reception.objects.using(alias).filter(customer_id__in=people.values('pk'),person_type='customer',workflow_version=2,registration_completed_at__isnull=True).update(workflow_version=1)
    Task.objects.using(alias).filter(source_customer_id__in=people.values('pk'),source_type__in=['followup','customer_followup','case','registration','call','invoice']).exclude(status__in=['done','cancelled']).update(status='cancelled')


class Migration(migrations.Migration):
    dependencies=[('customers','0026_preserve_arrivals_and_hiring_profiles'),('hr','0010_taskevent_snapshot')]
    operations=[migrations.AlterField(model_name='recordupdate',name='scope',field=models.CharField('تب',max_length=20,choices=[('reception','پذیرش'),('case','پرونده'),('hiring','استخدام')],db_index=True)),migrations.RunPython(align_candidates,migrations.RunPython.noop)]
