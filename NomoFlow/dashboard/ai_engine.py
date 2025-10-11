from marketing.models import Campaign
from django.db.models import Avg, Sum

def generate_ai_recommendations():
   
    recommendations = []
    campaigns = Campaign.objects.all()

    if not campaigns.exists():
        return ["🚀 No campaigns found. Start your first campaign to get AI insights."]

    avg_budget = campaigns.aggregate(avg=Avg("budget_total"))["avg"] or 0
    total_spend = campaigns.aggregate(total=Sum("budget_total"))["total"] or 0

    for c in campaigns:
        if c.status == "paused":
            recommendations.append(f"⚠️ Campaign '{c.name}' is paused. Consider resuming if results were good.")
        elif c.budget_total < avg_budget:
            recommendations.append(f"💸 Campaign '{c.name}' has below-average budget. Try increasing it.")
        elif c.status == "running":
            recommendations.append(f"🔥 '{c.name}' is performing well. Consider duplicating it for similar goals.")

    if total_spend > 5000:
        recommendations.append("📈 High spend detected — review ROI this week.")
    if len(recommendations) == 0:
        recommendations.append("✅ All campaigns are optimized. Great work!")

    return recommendations
