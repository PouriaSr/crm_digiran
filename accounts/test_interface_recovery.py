import os
import subprocess
import sys
from pathlib import Path
from django.contrib.auth.models import User
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from accounts.interface import catalog
from accounts.models import InterfaceChange


class SettingsHistoryTests(TestCase):
    def test_settings_opens_when_history_actor_was_deleted(self):
        admin=User.objects.create_superuser('settings_surviving_admin')
        actor=User.objects.create_user('settings_deleted_actor')
        InterfaceChange.objects.create(key='hub.tab.info',action='update',actor=actor)
        actor.delete()
        self.client.force_login(admin)
        response=self.client.get(reverse('accounts:interface_settings'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'کاربر حذف‌شده')
        self.assertContains(response,'<circle cx="12" cy="11.6" r="3"/>',html=False)


class CatalogEnvironmentTests(SimpleTestCase):
    def tearDown(self):
        catalog.cache_clear()

    def test_catalog_reads_under_ascii_host_locale(self):
        root=Path(__file__).resolve().parent.parent
        env=os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE='crm.settings',LC_ALL='C',LANG='C',PYTHONUTF8='0',PYTHONCOERCECLOCALE='0')
        result=subprocess.run([sys.executable,'-c',"import django;django.setup();from accounts.interface import catalog;assert len(catalog())>1000;print('CATALOG_OK')"],cwd=root,env=env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr[-1000:])
