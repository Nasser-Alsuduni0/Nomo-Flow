from django.urls import path
from .views import index, campaign_detail, kpis

urlpatterns = [
    path("", index, name="dashboard"),
    path("campaign/<int:pk>/", campaign_detail, name="campaign-detail"),
    path("kpis/", kpis, name="dashboard-kpis"),
]

