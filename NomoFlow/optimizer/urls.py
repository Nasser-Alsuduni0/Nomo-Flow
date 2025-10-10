from django.urls import path
from .views import run_automation

urlpatterns = [
    path("run/", run_automation, name="run_automation"),
]
