from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CampaignViewSet, kpis

router = DefaultRouter()
router.register("campaigns", CampaignViewSet, basename="campaign")

urlpatterns = [
    path("", include(router.urls)),
    path("kpis/", kpis, name="kpis"),
]
