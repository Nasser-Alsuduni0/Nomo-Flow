from django.urls import path
from . import views

urlpatterns = [
    path('', views.notifications_page, name='notifications-page'),
    path('toggle/<int:notification_id>/', views.toggle_notification, name='toggle-notification'),
    path('delete/<int:notification_id>/', views.delete_notification, name='delete-notification'),
]


