from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
    path('app/', views.app_entry, name='app_entry'),
    path('logout/', views.logout, name='logout'),
    path('disconnect/', views.disconnect, name='disconnect'),
]


