# debug_hub_call.py
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")
import django
django.setup()

from django.test.runner import DiscoverRunner
from django.test.utils import setup_test_environment, teardown_test_environment
from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
from customers.models import Customer
from customers.forms import HubCallForm
from calls.models import Call
from ads.models import AdSource

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False)
old_config = runner.setup_databases()

try:
    admin = User.objects.create_superuser("testadmin", "a@a.com", "123")
    source = AdSource.objects.create(phone_number="09120000000", label="تست")
    print(f"AdSource.pk = {source.pk}")
    print(f"AdSource count = {AdSource.objects.count()}")

    # ─── چک HubCallForm با customer_type = 'none' ───
    print("\n=== HubCallForm validation (customer_type='none') ===")
    data = {
        "mobile": "09123333333",
        "name": "تست",
        "call_type": "outgoing",
        "source": str(source.pk),
        "customer_type": "none",
        "status": "active",
        "notes": "تست",
        "follow_up_date": "",
    }
    form = HubCallForm(data=data)
    is_valid = form.is_valid()
    print(f"is_valid = {is_valid}")
    if not is_valid:
        print(f"errors = {dict(form.errors)}")
        # چک customer_type choices
        from customers.models import Customer
        print(f"\nCUSTOMER_TYPE_CHOICES = {getattr(Customer, 'CUSTOMER_TYPE_CHOICES', 'N/A')}")

    # ─── POST به view ───
    print("\n=== POST /customers/hub/call/ ===")
    client = Client()
    client.force_login(admin)
    response = client.post(reverse("customers:hub_submit_call"), data, follow=True)
    print(f"status = {response.status_code}")
    print(f"redirect chain = {response.redirect_chain}")

    call = Call.objects.filter(call_number="09123333333").first()
    print(f"Call created = {call is not None}")
    customer = Customer.all_objects.filter(mobile="09123333333").first()
    print(f"Customer created = {customer is not None}")

finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
