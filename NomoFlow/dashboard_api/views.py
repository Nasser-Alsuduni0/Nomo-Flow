from django.http import JsonResponse
from django.db.models import Sum, Count
from marketing.models import Campaign
from coupons.models import Coupon
from visitors.models import VisitorSession
from django.utils import timezone
from datetime import timedelta

def dashboard_metrics(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    campaigns = Campaign.objects.all()
    total_campaigns = campaigns.count()
    active_campaigns = campaigns.filter(status="running").count()
    total_budget = campaigns.aggregate(total=Sum("budget_total"))["total"] or 0
    total_coupons = Coupon.objects.count() if hasattr(Coupon, "objects") else 0
    total_visitors = VisitorSession.objects.filter(last_seen_at__gte=week_ago).count()

    data = {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_budget": float(total_budget),
        "total_coupons": total_coupons,
        "total_visitors": total_visitors,
    }
    return JsonResponse(data)


def dashboard_recommendations(request):
  
    recs = []
    total = Campaign.objects.count()

    if total == 0:
        recs.append("No campaigns found — create your first campaign to start gathering insights.")
    else:
        active = Campaign.objects.filter(status="running").count()
        paused = Campaign.objects.filter(status="paused").count()

        if active > paused:
            recs.append("Most campaigns are active — monitor ROAS to ensure efficiency.")
        if paused > 0:
            recs.append("Some campaigns are paused — consider reviewing their targeting or budget.")
        if total > 10:
            recs.append("Great! You’re managing 10+ campaigns — consider grouping by audience type.")

        recs += [
            "Try boosting TikTok Ads — engagement is trending high this week.",
            "Use limited-time coupons to create urgency and boost conversions.",
            "Schedule influencer collaborations on weekends — CTR usually peaks on Fridays.",
        ]

    return JsonResponse({"recommendations": recs})


def dashboard_campaigns(request):
    data = list(Campaign.objects.values("name", "status", "budget_total")[:10])
    return JsonResponse(data, safe=False)
