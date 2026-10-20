#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MODELS_PATH = BASE / 'customers' / 'models.py'

def fix_models():
    if not MODELS_PATH.exists():
        print("X customers/models.py not found.")
        return False
    
    content = MODELS_PATH.read_text(encoding='utf-8')
    
    # ۱. چک کردن و اضافه کردن فیلد is_lead به همراه فیلدهای دیگر
    if 'is_lead = models.BooleanField' not in content:
        # پیدا کردن خط کلاس Customer
        target = "class Customer(models.Model):"
        if target in content:
            # اضافه کردن فیلدها دقیقا بعد از تعریف کلاس
            insert_text = """
    is_lead = models.BooleanField('سرنخ', default=False)
    customer_type = models.CharField('نوع مشتری', max_length=20, choices=[('none', 'فاقد شرایط'), ('cash', 'نقدی'), ('cheque', 'چک'), ('installment', 'قسطی')], default='none')
    cheques_count = models.PositiveSmallIntegerField('تعداد چک', null=True, blank=True)
    installments_count = models.PositiveSmallIntegerField('تعداد اقسام', null=True, blank=True)
"""
            content = content.replace(target, target + insert_text)
            print("✓ Added missing fields to Customer model.")
    
    # ۲. چک کردن و اضافه کردن مدل Visit
    if 'class Visit(models.Model):' not in content:
        content += """

class Visit(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='visits', verbose_name='مشتری')
    visit_date = models.DateTimeField('تاریخ مراجعه', default=timezone.now)
    is_successful = models.BooleanField('مراحل با موفقیت طی شد؟', default=False)
    notes = models.TextField('یادداشت', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='ثبت‌کننده')
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'مراجعه حضوری'
        verbose_name_plural = 'مراجعات حضوری'
        ordering = ['-visit_date']
"""
        print("✓ Added Visit model.")
        
    MODELS_PATH.write_text(content, encoding='utf-8')
    return True

def main():
    print("🚀 Force fixing models and migrations...\n")
    if fix_models():
        print("\nRunning makemigrations...")
        subprocess.run([sys.executable, 'manage.py', 'makemigrations', 'customers'], check=False)
        print("\nRunning migrate...")
        subprocess.run([sys.executable, 'manage.py', 'migrate'], check=False)
        print("\n🎉 Done! Please restart your server.")
    else:
        print("X Failed to fix models.")

if __name__ == '__main__':
    main()
