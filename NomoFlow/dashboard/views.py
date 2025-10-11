from django.shortcuts import render, get_object_or_404
from marketing.models import Campaign
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import Merchant
from core.utils import get_current_merchant
from django.http import JsonResponse, HttpResponseBadRequest

def index(request):
    merchant = get_current_merchant(request)
    return render(request, "dashboard/overview.html", {
        'merchant': merchant
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
    # Placeholder static KPIs until wired to tracking data
    if campaign_id:
        return Response({"spend": 3100, "conversions": 28, "cpa": 18.5, "roas": 2.1})
    return Response({"spend_today": 0, "conversions": 0, "cpa": None, "roas": None})

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
    return render(request, "dashboard/feature_placeholder.html", {"title": "Purchase Display"})

def page_settings(request):
    return render(request, "dashboard/feature_placeholder.html", {"title": "Settings"})

def page_campaign(request):
    return render(request, "dashboard/campaign.html")


def switch_merchant(request):
    """Switch current merchant by id (POST or GET with ?merchant_id=)."""
    from core.utils import set_current_merchant
    mid = request.POST.get('merchant_id') or request.GET.get('merchant_id')
    if not mid:
        return HttpResponseBadRequest("merchant_id required")
    try:
        m = Merchant.objects.get(id=mid)
    except Merchant.DoesNotExist:
        return HttpResponseBadRequest("merchant not found")
    set_current_merchant(request, m)
    return JsonResponse({"ok": True, "merchant": {"id": m.id, "name": m.name, "store_id": m.salla_merchant_id}})

