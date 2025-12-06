from django.contrib import admin
from .models import Product, Customer, Order, OrderItem, CustomerInteraction


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'merchant', 'category', 'price', 'is_active', 'synced_at']
    list_filter = ['is_active', 'is_available', 'category', 'merchant']
    search_fields = ['name', 'description', 'salla_product_id', 'sku']
    readonly_fields = ['created_at', 'updated_at', 'synced_at']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'merchant', 'first_seen_at', 'last_seen_at']
    list_filter = ['merchant']
    search_fields = ['name', 'email', 'phone', 'salla_customer_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['salla_order_id', 'merchant', 'customer', 'total_amount', 'status', 'ordered_at']
    list_filter = ['status', 'merchant', 'ordered_at']
    search_fields = ['salla_order_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'product_name', 'quantity', 'price']
    list_filter = ['order__merchant']
    search_fields = ['product_name', 'salla_product_id']
    readonly_fields = ['created_at']


@admin.register(CustomerInteraction)
class CustomerInteractionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'product', 'interaction_type', 'occurred_at']
    list_filter = ['interaction_type', 'merchant', 'occurred_at']
    search_fields = ['product__name', 'customer__name', 'session_id']
    readonly_fields = ['occurred_at']
