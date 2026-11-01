from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Synchronize open workflow tasks without requesting reports for historical actions.'

    def handle(self, **options):
        from hr.task_automation import backfill
        backfill()
        self.stdout.write(self.style.SUCCESS('Workflow tasks synchronized.'))
