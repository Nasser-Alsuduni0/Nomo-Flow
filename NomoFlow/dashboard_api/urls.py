from django.urls import path
from . import views

urlpatterns = [
    path("metrics/", views.dashboard_metrics, name="dashboard_metrics"),
    path("recommendations/", views.dashboard_recommendations, name="dashboard_recommendations"),
    path("campaigns/", views.dashboard_campaigns, name="dashboard_campaigns"),
    path("performance/", views.dashboard_performance, name="dashboard_performance"),
    path("coupon-usage/", views.dashboard_coupon_usage, name="dashboard_coupon_usage"),
    path("traffic-sources/", views.dashboard_traffic_sources, name="dashboard_traffic_sources"),
]
