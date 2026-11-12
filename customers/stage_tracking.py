"""Submission metadata belongs to a visit, never to a shared customer's updated_at."""
from copy import deepcopy
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


def snapshot(form):
    instance = form.instance
    values = {field.attname: deepcopy(getattr(instance, field.attname))
              for field in instance._meta.concrete_fields
              if field.editable and not field.auto_created
              and not getattr(field, 'auto_now', False) and not getattr(field, 'auto_now_add', False)}
    section = getattr(form, 'structure_section', None)
    if section and instance.pk:
        from accounts.models import SectionRecord
        record = SectionRecord.objects.filter(section=section,
            content_type=ContentType.objects.get_for_model(instance), object_id=instance.pk).first()
        values['_configured'] = deepcopy(record.data) if record else {}
    return values


def record_submission(rec, stage, user, changed):
    now = timezone.now()
    completed = stage + '_completed'
    fields = [stage + '_last_saved_at', stage + '_last_saved_by']
    setattr(rec, fields[0], now)
    setattr(rec, fields[1], user)
    if not getattr(rec, completed + '_at'):
        setattr(rec, completed + '_at', now)
        setattr(rec, completed + '_by', user)
        fields += [completed + '_at', completed + '_by']
    elif changed:
        setattr(rec, stage + '_last_edited_at', now)
        setattr(rec, stage + '_last_edited_by', user)
        fields += [stage + '_last_edited_at', stage + '_last_edited_by']
    if stage == 'registration':
        rec.info_submitted = True
        fields.append('info_submitted')
    rec.save(update_fields=fields + ['updated_at'])
