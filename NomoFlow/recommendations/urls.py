from django.urls import path
from . import views
from . import embed_widget
from . import widgets

app_name = 'recommendations'

urlpatterns = [
    path('customer/<int:customer_id>/', views.recommend_for_customer, name='recommend_customer'),
    path('customer/', views.recommend_for_customer, name='recommend_customer_param'),
    path('product/<str:product_id>/', views.recommend_similar_products, name='recommend_product'),
    path('product/', views.recommend_similar_products, name='recommend_product_param'),
    path('trending/', views.recommend_trending, name='recommend_trending'),
    path('track/', views.track_interaction, name='track_interaction'),
    path('sync/products/', views.sync_products, name='sync_products'),
    path('sync/orders/', views.sync_orders, name='sync_orders'),
    path('embed.js', embed_widget.recommendations_widget_js, name='recommendations_widget_js'),
    path('snippet/', views.widget_snippet, name='widget_snippet'),
    path('widgets/', views.widget_snippets, name='widget_snippets'),
    # Separate widget endpoints
    path('widgets/recommended-for-you.js', widgets.recommended_for_you_js, name='widget_recommended_for_you'),
    path('widgets/similar-products.js', widgets.similar_products_js, name='widget_similar_products'),
    path('widgets/frequently-bought-together.js', widgets.frequently_bought_together_js, name='widget_frequently_bought'),
]

