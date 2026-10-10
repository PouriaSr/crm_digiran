from django.db import migrations


def create_default_categories(apps, schema_editor):
    """ساخت ۶ دسته‌ی پیش‌فرض"""
    Category = apps.get_model('products', 'Category')
    defaults = [
        ('mobile', '📱', 'موبایل و تبلت', 1),
        ('laptop', '💻', 'لپ‌تاپ و کامپیوتر', 2),
        ('accessory', '🎧', 'لوازم جانبی', 3),
        ('parts', '🔧', 'قطعات', 4),
        ('service', '🛠️', 'خدمات', 5),
        ('other', '📦', 'سایر', 99),
    ]
    for slug, icon, name, order in defaults:
        Category.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'icon': icon, 'order': order, 'is_active': True}
        )


def map_product_categories(apps, schema_editor):
    """کپی مقادیر category (رشته) به category_fk (FK)"""
    Product = apps.get_model('products', 'Product')
    Category = apps.get_model('products', 'Category')

    cat_map = {c.slug: c for c in Category.objects.all()}
    default_cat = cat_map.get('other')

    for product in Product.objects.all():
        old_slug = (product.category or '').strip()
        if old_slug and old_slug in cat_map:
            product.category_fk_id = cat_map[old_slug].id
        elif default_cat:
            product.category_fk_id = default_cat.id
        else:
            continue
        product.save(update_fields=['category_fk'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_category_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, reverse_noop),
        migrations.RunPython(map_product_categories, reverse_noop),
    ]
