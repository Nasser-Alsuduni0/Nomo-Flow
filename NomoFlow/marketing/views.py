from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Campaign
from .serializers import CampaignSerializer
from tracking.models import Event
from django.db.models import Sum, Count, Q, F

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by("-created_at")
    serializer_class = CampaignSerializer

@api_view(["GET"])
def kpis(request):
    cid = request.GET.get("campaign_id")

    qs = Event.objects.all()
    if cid: qs = qs.filter(campaign_id=cid)

    spend = qs.filter(kind="spend").aggregate(v=Sum("value"))["v"] or 0
    convs = qs.filter(kind="conversion").aggregate(c=Count("id"))["c"] or 0
    cpa   = (spend / convs) if convs else None
    revenue = qs.filter(kind="conversion").aggregate(v=Sum("value"))["v"] or 0
    roas = (revenue / spend) if spend else None

    if cid:
        return Response({"spend": spend, "conversions": convs, "cpa": cpa, "roas": roas})
    return Response({"spend_today": spend, "conversions": convs, "cpa": cpa, "roas": roas})
