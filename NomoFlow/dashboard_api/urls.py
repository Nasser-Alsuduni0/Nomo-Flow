from django.urls import path
from . import views

urlpatterns = [
    path("metrics/", views.dashboard_metrics, name="dashboard_metrics"),
    path("recommendations/", views.dashboard_recommendations, name="dashboard_recommendations"),
    path("campaigns/", views.dashboard_campaigns, name="dashboard_campaigns"),
]
