import requests
from django.conf import settings

TIKTOK_BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

def create_tiktok_campaign(name, budget):
    payload = {
        "advertiser_id": settings.TIKTOK_ADVERTISER_ID,
        "campaign_name": name,
        "budget_mode": "BUDGET_MODE_DAY",
        "budget": int(budget),
        "objective_type": "TRAFFIC",
    }
    headers = {"Access-Token": settings.TIKTOK_ACCESS_TOKEN}
    r = requests.post(f"{TIKTOK_BASE_URL}/campaign/create/", json=payload, headers=headers)
    return r.json()
