from __future__ import annotations

from typing import Optional
from django.http import HttpRequest
from .models import Merchant, SallaToken


SESSION_KEY_CURRENT_MERCHANT_ID = "current_merchant_id"


def set_current_merchant(request: HttpRequest, merchant: Merchant) -> None:
    request.session[SESSION_KEY_CURRENT_MERCHANT_ID] = merchant.id


def get_current_merchant(request: HttpRequest) -> Merchant:
    merchant: Optional[Merchant] = None

    try:
        mid = request.session.get(SESSION_KEY_CURRENT_MERCHANT_ID)
        if mid:
            merchant = Merchant.objects.filter(id=mid).first()
    except Exception:
        merchant = None

    if merchant is None:
        token = SallaToken.objects.select_related("merchant").first()
        if token and token.merchant:
            merchant = token.merchant

    if merchant is None:
        merchant = Merchant.objects.order_by("-created_at").first()

    if merchant is None:
        merchant, _ = Merchant.objects.get_or_create(
            salla_merchant_id="demo-store-123",
            defaults={"name": "Demo Store", "owner_email": "demo@example.com"},
        )

    return merchant


