from django.urls import path
from . import views

urlpatterns = [
    path('', views.notifications_page, name='notifications-page'),
    path('toggle/<int:notification_id>/', views.toggle_notification, name='toggle-notification'),
    path('edit/<int:notification_id>/', views.edit_notification, name='edit-notification'),
    path('delete/<int:notification_id>/', views.delete_notification, name='delete-notification'),
    path('feed/', views.public_feed, name='notifications-feed'),
    path('embed.js', views.embed_js, name='notifications-embed-js'),
    path('generate-snippet/', views.generate_snippet, name='generate-snippet'),
]


