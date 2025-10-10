from marketing.models import Campaign
from optimizer.tiktok_api import create_tiktok_campaign

def automate_campaigns():
    pending = Campaign.objects.filter(status="pending", primary_channel="tiktok")
    for c in pending:
        res = create_tiktok_campaign(c.name, c.budget_total)
        if res.get("code") == 0:  # success
            c.status = "running"
            c.external_ids["tiktok"] = res["data"]["campaign_id"]
        else:
            c.status = "failed"
        c.save()
