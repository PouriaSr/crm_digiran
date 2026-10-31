"""Preserve the source's name and number as recorded, independently of renames."""
from django.apps import apps
from django.db import models


class SourceSnapshotMixin(models.Model):
    source_phone_snapshot = models.CharField('شماره منبع هنگام ثبت', max_length=20, blank=True, default='', editable=False)
    source_label_snapshot = models.CharField('برچسب منبع هنگام ثبت', max_length=100, blank=True, default='', editable=False)
    source_snapshot_relation = 'source'

    class Meta:
        abstract = True

    @property
    def source_display(self):
        if not self.source_phone_snapshot:
            return 'ثبت نشده'
        if self.source_label_snapshot:
            return f'{self.source_phone_snapshot} ({self.source_label_snapshot})'
        return self.source_phone_snapshot

    def save(self, *args, **kwargs):
        relation = self.source_snapshot_relation
        source_id = getattr(self, relation + '_id')
        update_fields = kwargs.get('update_fields')
        writes_source = update_fields is None or bool({relation, relation + '_id'} & set(update_fields))
        changed = self._state.adding
        if not changed and writes_source:
            old_id = type(self)._base_manager.using(kwargs.get('using') or self._state.db).filter(pk=self.pk).values_list(relation + '_id', flat=True).first()
            changed = source_id != old_id
        if changed:
            source = apps.get_model('ads', 'AdSource').objects.using(kwargs.get('using') or self._state.db).filter(pk=source_id).values('phone_number', 'label').first()
            self.source_phone_snapshot = source['phone_number'] if source else ''
            self.source_label_snapshot = source['label'] if source else ''
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | {'source_phone_snapshot', 'source_label_snapshot'}
        return super().save(*args, **kwargs)
