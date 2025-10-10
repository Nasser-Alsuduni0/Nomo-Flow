from django.urls import path
from . import views

app_name = 'features'

urlpatterns = [
    path('email-collector/', views.email_collector_page, name='email_collector'),
    path('toggle/', views.toggle_feature, name='toggle_feature'),
    path('is-enabled/', views.is_feature_enabled, name='is_feature_enabled'),
    path('subscribe/', views.subscribe_email, name='subscribe_email'),
    path('unsubscribe/<int:pk>/', views.unsubscribe_email, name='unsubscribe_email'),
    path('delete/<int:pk>/', views.delete_subscriber, name='delete_subscriber'),
    path('export/', views.export_subscribers, name='export_subscribers'),
    path('email-embed.js', views.email_embed_js, name='email_embed_js'),
]
