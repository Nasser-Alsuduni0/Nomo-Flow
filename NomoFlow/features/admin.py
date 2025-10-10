from django.contrib import admin
from .models import Feature, MerchantFeature


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'created_at']
    search_fields = ['key', 'title']


@admin.register(MerchantFeature)
class MerchantFeatureAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'feature', 'is_enabled', 'created_at']
    list_filter = ['is_enabled', 'feature']
    search_fields = ['merchant__name', 'feature__key']
