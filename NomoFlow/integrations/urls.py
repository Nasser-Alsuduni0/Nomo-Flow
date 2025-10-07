from django.urls import path
from . import views

urlpatterns = [
    path("connect", views.salla_connect, name="salla_connect"),
    path("callback/", views.salla_callback, name="salla_callback"),
    path("webhook", views.salla_webhook, name="salla_webhook"),
]


