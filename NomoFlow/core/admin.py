from django.contrib import admin
from .models import Merchant, SallaToken, Event, Attribution, EmailSubscriber


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'salla_merchant_id', 'owner_email', 'created_at']
    search_fields = ['name', 'salla_merchant_id', 'owner_email']
    list_filter = ['created_at']


@admin.register(SallaToken)
class SallaTokenAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'expires_at', 'created_at']
    search_fields = ['merchant__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'merchant', 'occurred_at', 'received_at']
    list_filter = ['event_type', 'occurred_at']
    search_fields = ['merchant__name', 'event_type', 'salla_event_id']
    date_hierarchy = 'occurred_at'


@admin.register(Attribution)
class AttributionAdmin(admin.ModelAdmin):
    list_display = ['salla_order_id', 'merchant', 'revenue_sar', 'occurred_at']
    list_filter = ['occurred_at']
    search_fields = ['salla_order_id', 'salla_customer_id', 'merchant__name']
    date_hierarchy = 'occurred_at'


@admin.register(EmailSubscriber)
class EmailSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'merchant', 'consent', 'source', 'subscribed_at']
    list_filter = ['consent', 'source', 'subscribed_at']
    search_fields = ['email', 'name', 'merchant__name']
    readonly_fields = ['subscribed_at', 'unsubscribed_at']
    date_hierarchy = 'subscribed_at'
