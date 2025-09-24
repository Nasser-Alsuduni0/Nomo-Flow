import json
import time
import hmac
import hashlib
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.models import Merchant, SallaToken, Event
from integrations.models import Integration


@require_GET
def salla_connect(request):
    """
    Redirect merchant to Salla OAuth authorization.
    """
    client_id = settings.SALLA_CLIENT_ID
    redirect_uri = settings.SALLA_REDIRECT_URI or ((settings.PUBLIC_BASE_URL.rstrip("/") + "/salla/callback") if settings.PUBLIC_BASE_URL else "")
    scopes = " ".join(settings.SALLA_SCOPES)
    if not client_id or not redirect_uri:
        return HttpResponseBadRequest("Salla OAuth not configured")

    state = str(int(time.time()))  # could be a signed value if you need CSRF/state tracking
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    url = f"{settings.SALLA_OAUTH_AUTHORIZE_URL}?{urlencode(query)}"
    return redirect(url)


@require_GET
def salla_callback(request):
    """
    Handle Salla OAuth callback, exchange code for tokens, fetch store and persist.
    """
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code")

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.SALLA_CLIENT_ID,
        "client_secret": settings.SALLA_CLIENT_SECRET,
        "redirect_uri": settings.SALLA_REDIRECT_URI or ((settings.PUBLIC_BASE_URL.rstrip("/") + "/salla/callback") if settings.PUBLIC_BASE_URL else ""),
        "code": code,
    }
    token_resp = requests.post(settings.SALLA_OAUTH_TOKEN_URL, data=data, timeout=20)
    if token_resp.status_code != 200:
        return HttpResponseBadRequest("Token exchange failed")
    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in", 0)
    scope = token_json.get("scope")
    if not access_token:
        return HttpResponseBadRequest("No access token")

    # Fetch store info to create/link Merchant
    headers = {"Authorization": f"Bearer {access_token}"}

# 1) الموصى به: جلب هوية المستخدم والمتجر من UserInfo (أسرع وأضمن للربط)
    ui_resp = requests.get(settings.SALLA_USERINFO_URL, headers=headers, timeout=20)
    if ui_resp.status_code != 200:
     return HttpResponseBadRequest("Failed to fetch user info")
    ui = ui_resp.json()

# تحمّل اختلافات البُنى
    store_obj = ui.get("store") or ui.get("data", {}).get("store") or {}
    store_id   = str(store_obj.get("id") or ui.get("merchant_id") or ui.get("id") or "")
    store_name = store_obj.get("name") or ui.get("name") or "Salla Store"

    if not store_id:
    # خيار إضافي: جرّب Admin API كخطة بديلة
     si = requests.get(f"{settings.SALLA_API_BASE}/store/info", headers=headers, timeout=20)
    if si.status_code == 200:
        s = si.json().get("data") or si.json()
        store_id   = str(s.get("id") or "")
        store_name = s.get("name") or store_name

    if not store_id:
      return HttpResponseBadRequest("Missing store id")

    merchant, _ = Merchant.objects.get_or_create(
        salla_merchant_id=store_id,
        defaults={"name": store_name},
    )
    if merchant.name != store_name and store_name:
        merchant.name = store_name
        merchant.save(update_fields=["name"]) 

    expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in or 0))
    SallaToken.objects.update_or_create(
        merchant=merchant,
        defaults={
            "access_token": access_token,
            "refresh_token": refresh_token or "",
            "expires_at": expires_at,
            "scope": scope or "",
        },
    )

    Integration.objects.get_or_create(
        merchant=merchant,
        defaults={
            "api_base_url": settings.SALLA_API_BASE,
            "webhook_secret": settings.SALLA_WEBHOOK_SECRET or None,
        },
    )

    return JsonResponse({"status": "ok", "merchant_id": merchant.id, "salla_store_id": merchant.salla_merchant_id})


def _verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    if not (signature_header and secret):
        return False
    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)


@csrf_exempt
@require_POST
def salla_webhook(request):
    """
    Receive Salla webhooks, verify signature, store event, and return 200.
    URL should be configured per-merchant or globally at /salla/webhook
    """
    raw_body = request.body
    signature = request.headers.get("X-Salla-Signature", "")
    auth_header = request.headers.get("Authorization", "")

    # If you prefer per-merchant secrets, derive merchant from payload first, then fetch Integration.webhook_secret
    # For now, try global secret first
    secret = getattr(settings, "SALLA_WEBHOOK_SECRET", "")
    token_ok = False
    # Option 1: HMAC signature
    if _verify_signature(raw_body, signature, secret):
        token_ok = True
    # Option 2: Static bearer token in headers
    else:
        expected = getattr(settings, "SALLA_WEBHOOK_TOKEN", "")
        if expected and auth_header.startswith("Bearer ") and (auth_header.split(" ", 1)[1].strip() == expected):
            token_ok = True
    if not token_ok:
        return HttpResponseForbidden("Invalid signature or token")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    event_type = payload.get("event") or payload.get("type") or "unknown"
    data = payload.get("data") or {}

    # Try to link to merchant if payload contains store/merchant id
    merchant = None
    salla_store_id = str(payload.get("store_id") or data.get("store_id") or data.get("store", {}).get("id") or "")
    if salla_store_id:
        merchant = Merchant.objects.filter(salla_merchant_id=salla_store_id).first()

    # Easy Mode: handle app.store.authorize to persist tokens without OAuth redirect
    if event_type == "app.store.authorize":
        # Common payload fields (may vary by version)
        store_info = data.get("store") or data.get("merchant") or {}
        store_id = str(
            store_info.get("id")
            or data.get("store_id")
            or payload.get("store_id")
            or store_info.get("uuid")
            or ""
        )
        store_name = (
            store_info.get("name")
            or data.get("store_name")
            or "Salla Store"
        )
        if store_id:
            merchant, _ = Merchant.objects.get_or_create(
                salla_merchant_id=store_id,
                defaults={"name": store_name},
            )
            if store_name and merchant.name != store_name:
                merchant.name = store_name
                merchant.save(update_fields=["name"]) 

            access_token = data.get("access_token") or data.get("token")
            refresh_token = data.get("refresh_token") or ""
            expires_in = data.get("expires_in") or data.get("ttl") or 0
            scope = data.get("scope") or data.get("scopes") or ""
            if access_token:
                expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in or 0))
                SallaToken.objects.update_or_create(
                    merchant=merchant,
                    defaults={
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "expires_at": expires_at,
                        "scope": scope if isinstance(scope, str) else " ".join(scope) if scope else "",
                    },
                )
                Integration.objects.get_or_create(
                    merchant=merchant,
                    defaults={
                        "api_base_url": settings.SALLA_API_BASE,
                        "webhook_secret": settings.SALLA_WEBHOOK_SECRET or None,
                    },
                )

    # Only store event if merchant is identified to keep referential integrity
    if merchant:
        Event.objects.create(
            merchant=merchant,
            event_type=event_type,
            salla_event_id=str(payload.get("id") or ""),
            payload=payload,
            occurred_at=timezone.now(),
            received_at=timezone.now(),
        )

    return HttpResponse(status=200)


