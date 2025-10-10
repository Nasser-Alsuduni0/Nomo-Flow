from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="dashboard"),
    path("campaign/", views.page_campaign, name="page-campaign"),
    path("campaign/<int:pk>/", views.campaign_detail, name="campaign-detail"),
    path("kpis/", views.kpis, name="dashboard-kpis"),
    # Feature pages wired to dashboard shell
    path("live-view-counter/", views.page_live_view_counter, name="page-live-view-counter"),
    path("email-collector/", views.page_email_collector, name="page-email-collector"),
    path("discount-coupons/", views.page_discount_coupons, name="page-discount-coupons"),
    path("notifications/", views.page_notifications, name="page-notifications"),
    path("purchase-display/", views.page_purchase_display, name="page-purchase-display"),
    path("settings/", views.page_settings, name="page-settings"),
    path("switch-merchant/", views.switch_merchant, name="switch-merchant"),
]


