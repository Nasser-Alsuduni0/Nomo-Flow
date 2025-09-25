from django.shortcuts import render, get_object_or_404
from marketing.models import Campaign
from rest_framework.decorators import api_view
from rest_framework.response import Response

def index(request):
    return render(request, "dashboard/index.html")

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

