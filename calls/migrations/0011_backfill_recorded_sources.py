from django.db import migrations
from django.db.models import OuterRef, Subquery


def freeze_existing_sources(apps, schema_editor):
    """Best available source at upgrade time; do not invent unavailable history."""
    db = schema_editor.connection.alias
    Source = apps.get_model('ads', 'AdSource')
    Customer = apps.get_model('customers', 'Customer')
    Call = apps.get_model('calls', 'Call')
    Ad = apps.get_model('ads', 'Ad')
    Call.objects.using(db).filter(source_id__isnull=True).update(
        source_id=Subquery(Customer.objects.using(db).filter(pk=OuterRef('customer_id')).values('ad_source_id')[:1])
    )
    for Model, relation in ((Customer, 'ad_source_id'), (Call, 'source_id'), (Ad, 'source_id')):
        source = Source.objects.using(db).filter(pk=OuterRef(relation))
        Model.objects.using(db).filter(**{relation + '__isnull': False}, source_phone_snapshot='').update(
            source_phone_snapshot=Subquery(source.values('phone_number')[:1]),
            source_label_snapshot=Subquery(source.values('label')[:1]),
        )


class Migration(migrations.Migration):
    dependencies = [
        ('calls', '0010_call_source_call_source_label_snapshot_and_more'),
        ('customers', '0024_customer_source_label_snapshot_and_more'),
        ('ads', '0007_ad_source_label_snapshot_ad_source_phone_snapshot'),
    ]
    operations = [migrations.RunPython(freeze_existing_sources, migrations.RunPython.noop)]
