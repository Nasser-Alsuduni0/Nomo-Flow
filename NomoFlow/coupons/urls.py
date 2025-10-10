from django.urls import path
from . import views

app_name = 'coupons'

urlpatterns = [
    path('', views.coupons_page, name='coupons_page'),
    path('delete/<int:pk>/', views.delete_coupon, name='delete_coupon'),
    path('toggle/<int:pk>/', views.toggle_coupon, name='toggle_coupon'),
    path('edit/<int:pk>/', views.edit_coupon, name='edit_coupon'),
    path('feed/', views.public_coupons_feed, name='public_coupons_feed'),
    path('resolve-store', views.resolve_store, name='resolve_store'),
    path('check-sync/<int:pk>/', views.check_coupon_sync, name='check_coupon_sync'),
    path('embed.js', views.coupon_embed_js, name='coupon_embed_js'),
]


