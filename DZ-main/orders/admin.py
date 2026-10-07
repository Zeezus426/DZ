from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'commodity_grade', 'tonnage', 'purchase_price',
        'sale_price', 'status', 'counterparty', 'created_by', 'created_at',
    )
    list_filter = ('status', 'commodity_category', 'commodity_grade', 'created_at')
    search_fields = ('reference', 'counterparty', 'email', 'phone', 'website')
    readonly_fields = ('reference', 'created_by', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def save_model(self, request, obj, form, change):
        # Mirrors the portal: authorship is stamped, not typed.
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
