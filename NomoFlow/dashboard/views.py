from django.shortcuts import render, get_object_or_404
from marketing.models import Campaign
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import Merchant
from core.utils import get_current_merchant, set_current_merchant
from django.http import JsonResponse, HttpResponseBadRequest
from .ai_engine import generate_ai_recommendations


def index(request):
    merchant = get_current_merchant(request)
    kpis = ["Spend", "Revenue", "Coupons", "Active Offers"]
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

def page_settings(request):
    return render(request, "dashboard/feature_placeholder.html", {"title": "Settings"})

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

def page_ai_chat(request):
    return render(request, "dashboard/ai_chat.html", {"title": "AI Chat Assistant"})

def page_ai_analyzer(request):
    return render(request, "dashboard/ai_analyzer.html", {"title": "Performance Analyzer"})

def page_ai_insights(request):
    return render(request, "dashboard/ai_insights.html", {"title": "Audience Insights"})

def page_ai_automation(request):
    return render(request, "dashboard/ai_automation.html", {"title": "Automation Center"})

def page_ai_testing(request):
    return render(request, "dashboard/ai_testing.html", {"title": "A/B Testing Lab"})

def page_ai_forecast(request):
    return render(request, "dashboard/ai_forecast.html", {"title": "Campaign Forecast"})

def page_ai_creative(request):
    return render(request, "dashboard/ai_creative.html", {"title": "Creative Generator"})
