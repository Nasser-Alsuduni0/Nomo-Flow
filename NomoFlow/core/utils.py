from __future__ import annotations

from typing import Optional
from django.http import HttpRequest
from .models import Merchant, SallaToken


SESSION_KEY_CURRENT_MERCHANT_ID = "current_merchant_id"


def set_current_merchant(request: HttpRequest, merchant: Merchant) -> None:
    request.session[SESSION_KEY_CURRENT_MERCHANT_ID] = merchant.id


def get_current_merchant(request: HttpRequest) -> Optional[Merchant]:
    """
    Get current merchant from session.
    Returns None if no valid session exists.
    """
    merchant: Optional[Merchant] = None

    try:
        mid = request.session.get(SESSION_KEY_CURRENT_MERCHANT_ID)
        if mid:
            merchant = Merchant.objects.filter(id=mid, is_connected=True).first()
    except Exception:
        merchant = None

    return merchant


def clear_current_merchant(request: HttpRequest) -> None:
    """Clear current merchant from session (logout)"""
    try:
        if SESSION_KEY_CURRENT_MERCHANT_ID in request.session:
            merchant_id = request.session.get(SESSION_KEY_CURRENT_MERCHANT_ID)
            del request.session[SESSION_KEY_CURRENT_MERCHANT_ID]
            # Save session to ensure changes are persisted
            request.session.save()
            print(f"✅ Cleared session for merchant ID: {merchant_id}")
    except Exception as e:
        print(f"⚠️ Error clearing session: {e}")


