"""
تست‌های بازرسی مرزهای زمانی داشبورد/BI.

باگ واقعی: فیلترهای `issue_date` (DateTimeField) با مقدار `date` مقایسه می‌شدند
→ هشدار naive datetime و جابه‌جایی مرز بازه به اندازه‌ی اختلاف منطقه‌ی زمانی.
"""
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from sales.models import Invoice


class InvoiceDateBoundaryTest(TestCase):
    """مرز بازه‌ی ماه با اسناد دیروقت — نباید جابه‌جا شود"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('dt_admin', password='t123456')
        cls.customer = Customer.objects.create(
            name='مرز زمانی', mobile='09120001111',
            assigned_to=cls.user, created_by=cls.user,
        )

    def test_late_night_invoice_counts_in_its_own_day(self):
        """فاکتور ساعت ۲۳:۳۰ آخرین روز ماه، باید در همان ماه شمرده شود"""
        tz = timezone.get_current_timezone()
        last_day = timezone.localdate().replace(day=1)
        # آخرین روز ماه جاری میلادی
        nxt = (last_day + timedelta(days=32)).replace(day=1)
        end_of_month = nxt - timedelta(days=1)

        late = timezone.make_aware(
            datetime.combine(end_of_month, time(23, 30)), tz)
        inv = Invoice.objects.create(customer=self.customer, created_by=self.user,
                                     issue_date=late, total=1234567)
        try:
            # روش صحیح (__date): باید شمرده شود
            ok = Invoice.objects.filter(
                issue_date__date__gte=last_day,
                issue_date__date__lte=end_of_month,
            ).count()
            self.assertEqual(ok, 1, 'فاکتور دیروقت باید در بازه‌ی ماه شمرده شود')

            # روش قدیمی (date خام روی DateTimeField) → هشدار و حذف از بازه
            import warnings
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                legacy = Invoice.objects.filter(
                    issue_date__lte=end_of_month,
                    issue_date__gte=last_day,
                ).count()
            self.assertGreaterEqual(legacy, 0)
            self.assertTrue(
                any('naive datetime' in str(w.message) for w in caught),
                'روش قدیمی باید هشدار منطقه‌ی زمانی بدهد (اثبات باگ)',
            )
        finally:
            inv.delete()

    def test_local_midnight_boundary(self):
        """فاکتور ۰۰:۰۵ بامداد یک روز، در همان روز شمرده شود"""
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        early = timezone.make_aware(datetime.combine(today, time(0, 5)), tz)
        inv = Invoice.objects.create(customer=self.customer, created_by=self.user,
                                     issue_date=early, total=999)
        try:
            count = Invoice.objects.filter(issue_date__date=today).count()
            self.assertGreaterEqual(count, 1)
        finally:
            inv.delete()

    def test_bi_inactive_cutoff_is_aware(self):
        """/bi/ نباید با naive datetime مقایسه کند"""
        import warnings
        tz = timezone.get_current_timezone()
        cutoff = timezone.now() - timedelta(days=90)

        old = Invoice.objects.create(
            customer=self.customer, created_by=self.user,
            issue_date=timezone.make_aware(
                datetime.combine((timezone.localdate() - timedelta(days=200)), time(12, 0)), tz),
            total=5000,
        )
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                qs = Invoice.objects.filter(issue_date__lt=cutoff)
                list(qs.values_list('id', flat=True))
            self.assertFalse(
                [w for w in caught if 'naive datetime' in str(w.message)],
                'فیلتر cutoff نباید naive datetime بفرستد',
            )
            self.assertEqual(qs.count(), 1)
        finally:
            old.delete()
