from django.contrib import admin
from crm.pagination import PAGE_SIZE

# Apply the same record-list limit to built-in and application admin lists.
admin.ModelAdmin.list_per_page = PAGE_SIZE
admin.ModelAdmin.list_max_show_all = PAGE_SIZE
