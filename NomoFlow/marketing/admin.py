from django.contrib import admin
from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'objective', 'primary_channel', 'status', 'budget_total', 'created_at']
    list_filter = ['objective', 'primary_channel', 'status', 'created_at']
    search_fields = ['name', 'product_url']
    list_editable = ['status']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'objective', 'product_url')
        }),
        ('Campaign Settings', {
            'fields': ('primary_channel', 'budget_total', 'status')
        }),
        ('Timing', {
            'fields': ('end_at',),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': ('external_ids',),
            'classes': ('collapse',)
        }),
    )
