# نصب اصلاحیه چیدمان نسخه ۵۹

این اصلاحیه باید پس از نسخه ۵۸ اجرا شود. تراز سراسری ناخواسته‌ای را که جای دکمه جستجو و بعضی دکمه‌های فیلتر/پذیرش را تغییر می‌داد حذف می‌کند، بدون اینکه نمایش پیام‌ها زیر فیلد یا اصلاحات تایمر و باشگاه مشتریان حذف شوند.

1. فایل `scripts/update_customer_workflow_v59.py` را کنار `manage.py` آپلود کنید.
2. در **Setup Python App**، بخش **Execute Python Script**، نام زیر را اجرا کنید:

   ```text
   update_customer_workflow_v59.py
   ```

3. پس از پیام `SUCCESS: V59 installed` صفحه را با `Ctrl+F5` تازه‌سازی کنید.

گزارش در `logs/workflow_v59_update.log` و نسخه پشتیبان در `backups/workflow-v59-*` ذخیره می‌شود.
