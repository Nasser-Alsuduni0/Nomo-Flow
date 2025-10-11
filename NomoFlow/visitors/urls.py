from django.urls import path
from . import views

app_name = 'visitors'

urlpatterns = [
    path('live-view-counter/', views.live_view_counter_page, name='live_view_counter'),
    path('toggle/', views.toggle_feature, name='toggle_feature'),
    path('is-enabled/', views.is_feature_enabled, name='is_feature_enabled'),
    path('track/', views.track_visit, name='track_visit'),
    path('live-count/', views.get_live_count, name='get_live_count'),
    path('live-counter.js', views.live_counter_embed_js, name='live_counter_embed_js'),
]
