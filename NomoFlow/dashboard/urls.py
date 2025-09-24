from django.urls import path
from .views import index, campaign_detail

urlpatterns = [
    path("", index, name="dashboard"),
    path("campaign/<int:pk>/", campaign_detail, name="campaign-detail"),
]

