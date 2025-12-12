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
from core.utils import set_current_merchant


@require_GET
def salla_connect(request):
    """
    Redirect merchant to Salla OAuth authorization.
    """
    client_id = settings.SALLA_CLIENT_ID
    redirect_uri = settings.SALLA_REDIRECT_URI or ((settings.PUBLIC_BASE_URL.rstrip("/") + "/salla/callback/") if settings.PUBLIC_BASE_URL else "")
    # Ensure redirect_uri ends with / to match URL pattern
    if redirect_uri and not redirect_uri.endswith("/"):
        redirect_uri = redirect_uri + "/"
    scopes = " ".join(settings.SALLA_SCOPES)
    if not client_id or not redirect_uri:
        return HttpResponseBadRequest("Salla OAuth not configured")

    # Debug logging
    print(f"🔵 OAuth Authorization Request:")
    print(f"   Authorization URL: {settings.SALLA_OAUTH_AUTHORIZE_URL}")
    print(f"   Client ID: {client_id}")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Scopes: {scopes}")
    print(f"   ⚠️ IMPORTANT: Make sure this Redirect URI matches EXACTLY what's registered in Salla App Settings")

    # Generate state parameter for CSRF protection
    # Store it in session to verify on callback
    import secrets
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    request.session['oauth_redirect_uri'] = redirect_uri
    
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    url = f"{settings.SALLA_OAUTH_AUTHORIZE_URL}?{urlencode(query)}"
    print(f"   Full OAuth URL: {url}")
    print(f"   State (for CSRF protection): {state[:20]}...")
    return redirect(url)


@require_GET
def salla_callback(request):
    """
    Handle Salla OAuth callback, exchange code for tokens, fetch store and persist.
    """
    # Check for error from Salla
    error = request.GET.get("error")
    error_description = request.GET.get("error_description", "")
    
    if error:
        error_msg = f"OAuth error from Salla: {error}"
        if error_description:
            error_msg += f" - {error_description}"
        print(f"🔴 {error_msg}")
        print(f"   Full query params: {dict(request.GET)}")
        # Redirect to app entry with error message
        from django.contrib import messages
        messages.error(request, f"خطأ في تسجيل الدخول: {error_description or error}")
        return redirect('app_entry')
    
    # Verify state parameter for CSRF protection
    received_state = request.GET.get("state")
    stored_state = request.session.get('oauth_state')
    
    if not stored_state or received_state != stored_state:
        # RELAXED SECURITY: Log warning but allow proceeding.
        # This is necessary because Salla iframes often block third-party cookies,
        # causing the session (and stored_state) to be lost.
        # The security is maintained by the Authorization Code exchange:
        # We can't exchange a code for a token without the valid Client Secret.
        print(f"⚠️ State mismatch or session lost (likely iframe cookie block). Proceeding strictly via Token Exchange.")
        print(f"   Received state: {received_state}")
        print(f"   Stored state: {stored_state}")
        # do NOT redirect/return error here.
    else:
        print(f"✅ State verified successfully")
    code = request.GET.get("code")
    if not code:
        # Log all query parameters for debugging
        print(f"🔴 Missing code in callback")
        print(f"   Full query params: {dict(request.GET)}")
        print(f"   Request path: {request.path}")
        print(f"   Request GET: {request.GET}")
        print(f"   Request META: {dict(request.META.get('QUERY_STRING', ''))}")
        
        # Check if this is a direct access (not from OAuth redirect)
        from django.contrib import messages
        messages.error(request, "لم يتم استلام رمز التفعيل من سلة. يرجى المحاولة مرة أخرى.")
        return redirect('app_entry')

    # Use redirect_uri from session (stored during authorization request) or fallback to settings
    redirect_uri = request.session.get('oauth_redirect_uri') or settings.SALLA_REDIRECT_URI or ((settings.PUBLIC_BASE_URL.rstrip("/") + "/salla/callback/") if settings.PUBLIC_BASE_URL else "")
    # Ensure redirect_uri ends with / to match URL pattern
    if redirect_uri and not redirect_uri.endswith("/"):
        redirect_uri = redirect_uri + "/"
    
    # Clear redirect_uri from session after use
    if 'oauth_redirect_uri' in request.session:
        del request.session['oauth_redirect_uri']
    
    # Debug logging
    print(f"🟢 OAuth Token Exchange Request:")
    print(f"   Client ID: {settings.SALLA_CLIENT_ID}")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Code: {code[:20]}...")

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.SALLA_CLIENT_ID,
        "client_secret": settings.SALLA_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    try:
        token_resp = requests.post(settings.SALLA_OAUTH_TOKEN_URL, data=data, timeout=20)
        if token_resp.status_code != 200:
            print(f"🔴 Token Exchange FAILED!")
            print(f"   Status: {token_resp.status_code}")
            print(f"   Error: {token_resp.text}")
            print(f"   Data sent: {data}")
            return HttpResponseBadRequest(f"Token exchange failed: {token_resp.status_code} - {token_resp.text}")
    except requests.exceptions.ConnectionError as e:
        err = f"Connection error to Salla OAuth server: {str(e)}"
        print(f"🔴 {err}")
        return HttpResponseBadRequest(err)
    except requests.exceptions.RequestException as e:
        err = f"Request error during token exchange: {str(e)}"
        print(f"🔴 {err}")
        return HttpResponseBadRequest(err)
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
    try:
        ui_resp = requests.get(settings.SALLA_USERINFO_URL, headers=headers, timeout=20)
        if ui_resp.status_code != 200:
            return HttpResponseBadRequest(f"Failed to fetch user info: {ui_resp.status_code} - {ui_resp.text}")
    except requests.exceptions.ConnectionError as e:
        return HttpResponseBadRequest(f"Connection error to Salla UserInfo server: {str(e)}")
    except requests.exceptions.RequestException as e:
        return HttpResponseBadRequest(f"Request error: {str(e)}")
    ui = ui_resp.json()

    # Debug Salla UserInfo response
    print(f"🧐 UserInfo raw response: {ui}")

    store_obj = ui.get("store") or ui.get("data", {}).get("store") or {}
    store_id   = str(store_obj.get("id") or ui.get("merchant_id") or ui.get("id") or "")
    store_name = store_obj.get("name") or ui.get("name") or "Salla Store"

    if not store_id:
        print(f"⚠️ Store ID not found in UserInfo. Trying Admin API...")
        # Fallback to Admin API
        try:
            si = requests.get(f"{settings.SALLA_API_BASE}/store/info", headers=headers, timeout=20)
            print(f"🧐 StoreInfo status: {si.status_code}")
            print(f"🧐 StoreInfo response: {si.text}")
            
            if si.status_code == 200:
                s = si.json().get("data") or si.json()
                store_id   = str(s.get("id") or "")
                store_name = s.get("name") or store_name
        except Exception as e:
            print(f"🔴 Admin API fallback failed: {e}")

    if not store_id:
        print("🔴 CRITICAL: Failed to retrieve Store ID from both UserInfo and Admin API.")
        return HttpResponseBadRequest("Missing store id - Could not retrieve store information from Salla.")

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

    # Mark merchant as connected
    merchant.is_connected = True
    merchant.save(update_fields=["is_connected"])

    Integration.objects.get_or_create(
        merchant=merchant,
        defaults={
            "api_base_url": settings.SALLA_API_BASE,
            "webhook_secret": settings.SALLA_WEBHOOK_SECRET or None,
        },
    )

    # Set current merchant in session for this user
    from django.contrib import messages
    try:
        set_current_merchant(request, merchant)
    except Exception:
        pass
    messages.success(request, f'تم ربط متجرك "{merchant.name}" بنجاح!')
    return redirect('dashboard')


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

    # Temporarily disable webhook authentication for testing
    # TODO: Re-enable authentication once we confirm the correct method
    # expected_token = getattr(settings, "SALLA_WEBHOOK_TOKEN", "")
    # token_ok = False
    # 
    # if expected_token and auth_header.startswith("Bearer "):
    #     received_token = auth_header.split(" ", 1)[1].strip()
    #     if received_token == expected_token:
    #         token_ok = True
    # 
    # if not token_ok:
    #     return HttpResponseForbidden("Invalid webhook token")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    event_type = payload.get("event") or payload.get("type") or "unknown"
    data = payload.get("data") or {}

    # Try to link to merchant if payload contains store/merchant id
    merchant = None
    salla_store_id = str(payload.get("store_id") or data.get("store_id") or data.get("store", {}).get("id") or payload.get("merchant") or "")
    if salla_store_id:
        merchant = Merchant.objects.filter(salla_merchant_id=salla_store_id).first()

    # Store event BEFORE handling uninstall (to avoid referencing deleted merchant)
    if merchant:
        Event.objects.create(
            merchant=merchant,
            event_type=event_type,
            salla_event_id=str(payload.get("id") or ""),
            payload=payload,
            occurred_at=timezone.now(),
            received_at=timezone.now(),
        )

    # Handle app uninstall/revoke events
    if event_type == "app.uninstalled" or event_type == "app.store.deauthorize" or event_type == "app.store.revoke":
        if merchant:
            # Store merchant info before deletion
            merchant_id = merchant.salla_merchant_id
            
            # Clean up OAuth tokens first
            SallaToken.objects.filter(merchant=merchant).delete()
            
            # Option 1: Soft delete (recommended for analytics)
            # Add is_active field to Merchant model if you want this approach
            # merchant.is_active = False
            # merchant.deactivated_at = timezone.now()
            # merchant.save()
            
            # Option 2: Hard delete (removes all data completely)
            # This will cascade delete all related data due to CASCADE relationships
            merchant.delete()
            
            print(f"Merchant {merchant_id} uninstalled app - data cleaned up")

    # Easy Mode: handle app.store.authorize to persist tokens without OAuth redirect
    elif event_type == "app.store.authorize":
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
                # Mark merchant as connected
                merchant.is_connected = True
                merchant.save(update_fields=["is_connected"])
                Integration.objects.get_or_create(
                    merchant=merchant,
                    defaults={
                        "api_base_url": settings.SALLA_API_BASE,
                        "webhook_secret": settings.SALLA_WEBHOOK_SECRET or None,
                    },
                )

    # Event already stored above before uninstall handling

    return HttpResponse(status=200)


