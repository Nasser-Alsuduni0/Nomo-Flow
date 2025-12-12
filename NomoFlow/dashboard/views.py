from django.shortcuts import render, get_object_or_404, redirect
from marketing.models import Campaign
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import Merchant
from core.utils import get_current_merchant, set_current_merchant
from django.http import JsonResponse, HttpResponseBadRequest
from .ai_engine import generate_ai_recommendations
from features.models import Feature, MerchantFeature


def index(request):
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('app_entry')
    kpis = ["Visitors", "Page Views", "Coupons", "Revenue"]
    return render(request, "dashboard/overview.html", {
        'merchant': merchant,
        'kpis': kpis
    })


def campaign_detail(request, pk: int):
    c = get_object_or_404(Campaign, pk=pk)
    return render(request, "dashboard/campaign_detail.html", {
        "campaign_id": c.id,
        "campaign_name": c.name,
    })


@api_view(["GET"])
def kpis(request):
    campaign_id = request.GET.get("campaign_id")
    if campaign_id:
        return Response({
            "spend": 3100,
            "conversions": 28,
            "cpa": 18.5,
            "roas": 2.1
        })
    return Response({
        "spend_today": 0,
        "conversions": 0,
        "cpa": None,
        "roas": None
    })


def page_live_view_counter(request):
    from visitors.views import live_view_counter_page
    return live_view_counter_page(request)

def page_email_collector(request):
    from features.views import email_collector_page
    return email_collector_page(request)

def page_discount_coupons(request):
    from coupons.views import coupons_page
    return coupons_page(request)

def page_notifications(request):
    from notifications.views import notifications_page
    return notifications_page(request)

def page_purchase_display(request):
    from features.views import purchase_display_page

    return purchase_display_page(request)

def page_campaign(request):
    return render(request, "dashboard/campaign.html")


def page_ai_recommendations(request):
  
    return render(request, "dashboard/ai_recommendations.html")


def ai_recommendations(request):
 
    try:
        data = {"recommendations": generate_ai_recommendations()}
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def switch_merchant(request):
    mid = request.POST.get('merchant_id') or request.GET.get('merchant_id')
    if not mid:
        return HttpResponseBadRequest("merchant_id required")
    try:
        m = Merchant.objects.get(id=mid)
    except Merchant.DoesNotExist:
        return HttpResponseBadRequest("merchant not found")
    set_current_merchant(request, m)
    return JsonResponse({
        "ok": True,
        "merchant": {
            "id": m.id,
            "name": m.name,
            "store_id": m.salla_merchant_id
        }
    })

def page_recommendations(request):
    """Recommendations management page"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    # Get stats
    from recommendations.models import Product, Customer, Order, CustomerInteraction
    
    total_products = Product.objects.filter(merchant=merchant).count()
    total_customers = Customer.objects.filter(merchant=merchant).count()
    total_orders = Order.objects.filter(merchant=merchant).count()
    total_interactions = CustomerInteraction.objects.filter(merchant=merchant).count()
    
    # Get recent products
    recent_products = Product.objects.filter(merchant=merchant, is_active=True).order_by('-synced_at')[:10]
    
    context = {
        'merchant': merchant,
        'total_products': total_products,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_interactions': total_interactions,
        'recent_products': recent_products,
    }
    
    return render(request, "dashboard/recommendations.html", context)


def page_features(request):
    """Features control panel page"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    # Define the features we want to display
    feature_configs = [
        {
            'key': 'notifications',
            'title': 'Notifications',
            'description': 'Send personalized notifications to your store\'s customers to increase engagement with special offers.',
            'icon': 'bi-bell',
            'icon_color': '#0ea5e9',
            'settings_url': '/dashboard/notifications/',
        },
        {
            'key': 'coupons',
            'title': 'Discount Coupons',
            'description': 'Create attractive discount coupons and send them via notifications to customers to encourage purchases.',
            'icon': 'bi-tag',
            'icon_color': '#10b981',
            'settings_url': '/dashboard/discount-coupons/',
        },
        {
            'key': 'live_counter',
            'title': 'Live Visitor Counter',
            'description': 'Display the current number of visitors in your store to show its popularity and encourage purchases.',
            'icon': 'bi-people',
            'icon_color': '#f59e0b',
            'settings_url': '/dashboard/live-view-counter/',
        },
        {
            'key': 'email_collector',
            'title': 'Email Collector',
            'description': 'A pop-up window to collect visitor emails and build your marketing database.',
            'icon': 'bi-envelope',
            'icon_color': '#0ea5e9',
            'settings_url': '/dashboard/email-collector/',
        },
            {
                'key': 'recent_purchases',
                'title': 'Purchase Display',
                'description': 'Display an automatic message like \'Mohammed from Jeddah bought a product 5 minutes ago\' to encourage purchases.',
                'icon': 'bi-cart-check',
                'icon_color': '#f59e0b',
                'settings_url': '/dashboard/purchase-display/',
            },
            {
                'key': 'recommendations',
                'title': 'Product Recommendations',
                'description': 'AI-powered product recommendations using collaborative filtering and content-based filtering to boost sales.',
                'icon': 'bi-lightbulb',
                'icon_color': '#8b5cf6',
                'settings_url': '/dashboard/recommendations/',
            },
    ]
    
    # Get or create features and their merchant feature status
    features_list = []
    for config in feature_configs:
        feature, _ = Feature.objects.get_or_create(
            key=config['key'],
            defaults={
                'title': config['title'],
                'description': config['description']
            }
        )
        
        merchant_feature, _ = MerchantFeature.objects.get_or_create(
            merchant=merchant,
            feature=feature,
            defaults={'is_enabled': False}
        )
        
        # Check if feature is ready (has required setup)
        is_ready = True
        if config['key'] == 'notifications':
            from notifications.models import PopupNotification
            is_ready = PopupNotification.objects.filter(merchant=merchant).exists()
        elif config['key'] == 'coupons':
            from coupons.models import Coupon
            is_ready = Coupon.objects.filter(merchant=merchant).exists()
        elif config['key'] == 'recommendations':
            from recommendations.models import Product
            is_ready = Product.objects.filter(merchant=merchant).exists()
        
        features_list.append({
            'key': config['key'],
            'title': config['title'],
            'description': config['description'],
            'icon': config['icon'],
            'icon_color': config['icon_color'],
            'settings_url': config['settings_url'],
            'is_enabled': merchant_feature.is_enabled,
            'is_ready': is_ready,
        })
    
    context = {
        'merchant': merchant,
        'features': features_list,
    }
    
    return render(request, "dashboard/features.html", context)


def page_settings(request):
    """Account settings page"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('app_entry')
    
    # Get data statistics
    from recommendations.models import Product, Customer, Order, CustomerInteraction
    
    total_products = Product.objects.filter(merchant=merchant).count()
    total_customers = Customer.objects.filter(merchant=merchant).count()
    total_orders = Order.objects.filter(merchant=merchant).count()
    total_interactions = CustomerInteraction.objects.filter(merchant=merchant).count()
    
    context = {
        'merchant': merchant,
        'total_products': total_products,
        'total_customers': total_customers,
        'total_orders': total_orders,
        'total_interactions': total_interactions,
    }
    
    return render(request, "dashboard/settings.html", context)
