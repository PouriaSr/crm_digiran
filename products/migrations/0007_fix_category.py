from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_migrate_categories_data'),
    ]

    operations = [
        # ۱. حذف فیلد قدیمی CharField
        migrations.RemoveField(
            model_name='product',
            name='category',
        ),
        # ۲. rename category_fk → category
        migrations.RenameField(
            model_name='product',
            old_name='category_fk',
            new_name='category',
        ),
        # ۳. غیر-nullable کردن
        migrations.AlterField(
            model_name='product',
            name='category',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='products',
                to='products.category',
                verbose_name='دسته\u200cبندی',
            ),
        ),
    ]
