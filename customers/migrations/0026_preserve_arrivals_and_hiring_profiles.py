from django.db import migrations
from django.db.models.functions import Coalesce


def preserve_existing_workflow(apps, schema_editor):
    db = schema_editor.connection.alias
    Reception = apps.get_model('customers', 'Reception')
    Application = apps.get_model('customers', 'HiringApplication')
    # Existing wait values retain their old meaning; no processing/interview
    # durations are invented for work performed before this workflow existed.
    Reception.objects.using(db).update(arrived_at=Coalesce('wait_started_at', 'created_at'), timing_version=2)
    batch = []
    for rec in Reception.objects.using(db).filter(person_type='interviewer').iterator(chunk_size=500):
        batch.append(Application(reception_id=rec.pk, current_arrived_at=rec.arrived_at))
        if len(batch) == 500:
            Application.objects.using(db).bulk_create(batch, ignore_conflicts=True)
            batch = []
    if batch:
        Application.objects.using(db).bulk_create(batch, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [('customers', '0025_hiringadsequence_reception_arrived_at_and_more')]
    operations = [migrations.RunPython(preserve_existing_workflow, migrations.RunPython.noop)]
