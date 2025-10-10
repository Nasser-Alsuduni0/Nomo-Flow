from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
from .models import Coupon
from .forms import CouponForm
from core.models import Merchant, SallaToken
from core.utils import get_current_merchant
from django.conf import settings
from datetime import timedelta
import requests


def get_merchant(request):
    """Resolve current merchant using session-aware resolver."""
    return get_current_merchant(request)


@ensure_csrf_cookie
def coupons_page(request):
    """Main coupons page with create form and list of coupons"""
    merchant = get_merchant(request)
    
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.merchant = merchant
            coupon.save()

            # Attempt to create the coupon in Salla Admin API (best-effort)
            try:
                _create_coupon_in_salla(merchant, coupon)
            except Exception as e:
                # Best-effort: do not block local creation if Salla call fails
                print(f"⚠️ Salla coupon sync failed: {e}")
            messages.success(request, f'Coupon "{coupon.code}" created successfully!')
            return redirect('coupons:coupons_page')
    else:
        form = CouponForm()
    
    coupons = Coupon.objects.filter(merchant=merchant).order_by('-created_at')
    
    return render(request, 'coupons/coupons.html', {
        'form': form,
        'coupons': coupons,
        'merchant': merchant
    })


@require_POST
def delete_coupon(request, pk):
    """Delete a coupon"""
    try:
        merchant = get_merchant(request)
        coupon = get_object_or_404(Coupon, pk=pk, merchant=merchant)
        code = coupon.code
        
        # Try to delete from Salla first (best-effort)
        try:
            _delete_coupon_in_salla(merchant, coupon)
        except Exception as e:
            print(f"⚠️ Salla coupon deletion failed: {e}")
        
        # Delete from local database
        coupon.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon "{code}" deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@require_POST
def toggle_coupon(request, pk):
    """Toggle coupon active status"""
    merchant = get_merchant(request)
    coupon = get_object_or_404(Coupon, pk=pk, merchant=merchant)
    
    # Toggle is_active status
    coupon.is_active = not coupon.is_active
    coupon.save()
    
    # Sync status to Salla (best-effort)
    try:
        _update_coupon_in_salla(merchant, coupon)
    except Exception as e:
        print(f"⚠️ Salla status sync failed: {e}")
    
    return JsonResponse({
        'success': True,
        'is_active': coupon.is_active
    })


def edit_coupon(request, pk):
    """Edit a coupon"""
    merchant = get_merchant(request)
    coupon = get_object_or_404(Coupon, pk=pk, merchant=merchant)
    
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            updated_coupon = form.save()
            
            # Try to sync update to Salla (best-effort)
            try:
                _update_coupon_in_salla(merchant, updated_coupon)
            except Exception as e:
                print(f"⚠️ Salla coupon update sync failed: {e}")
            
            return JsonResponse({
                'success': True,
                'message': 'Coupon updated successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    # Return coupon data for editing (GET request)
    return JsonResponse({
        'success': True,
        'coupon': {
            'id': coupon.id,
            'code': coupon.code,
            'discount_kind': coupon.discount_kind,
            'amount': str(coupon.amount),
            'max_discount_amount': str(coupon.max_discount_amount) if coupon.max_discount_amount else '',
            'start_date': coupon.start_date.strftime('%Y-%m-%d') if coupon.start_date else '',
            'expires_at': coupon.expires_at.strftime('%Y-%m-%d') if coupon.expires_at else '',
            'free_shipping': coupon.free_shipping,
            'exclude_discounted': coupon.exclude_discounted,
            'min_cart': str(coupon.min_cart) if coupon.min_cart else '',
            'max_uses': coupon.max_uses,
            'per_customer_limit': coupon.per_customer_limit,
            'is_active': coupon.is_active,
        }
    })


@csrf_exempt
def public_coupons_feed(request):
    """Public API endpoint to get active coupons for a store"""
    store_id = request.GET.get('store_id')
    
    # Debug logging
    print(f"🔍 Coupon Feed Request:")
    print(f"   Received store_id: '{store_id}'")
    print(f"   Type: {type(store_id)}")
    
    if not store_id:
        print(f"   ❌ No store_id provided")
        return JsonResponse({'coupons': []})
    
    # Check if store_id contains template syntax (not replaced by Salla)
    if '{{' in store_id or '}}' in store_id:
        print(f"   ❌ Template variable not replaced by Salla: {store_id}")
        return JsonResponse({'coupons': [], 'error': 'Template variable not replaced'})
    
    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
        print(f"   ✅ Found merchant: {merchant.name}")
    except Merchant.DoesNotExist:
        print(f"   ❌ No merchant found with ID: {store_id}")
        return JsonResponse({'coupons': []})
    
    now = timezone.now()
    
    # Get active coupons that haven't expired and are not paused
    coupons = Coupon.objects.filter(
        merchant=merchant,
        is_active=True  # Only show active (not paused) coupons
    ).exclude(
        expires_at__lt=now
    ).values(
        'id', 'code', 'discount_kind', 'amount', 
        'max_discount_amount', 'free_shipping', 
        'min_cart', 'expires_at'
    )
    
    response = JsonResponse({
        'coupons': list(coupons)
    })
    
    # Add CORS headers
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    
    return response


def _create_coupon_in_salla(merchant: Merchant, coupon: Coupon) -> None:
    """Best-effort create the coupon in Salla Admin API and store the returned id.

    - Requires the merchant to have an active SallaToken (OAuth install).
    - Tries a few likely endpoints; succeeds on the first 200/201 response.
    - Never raises to caller; meant to be used inside a try/except.
    """
    # If already linked, skip
    if coupon.salla_coupon_id:
        return

    token = SallaToken.objects.filter(merchant=merchant).first()
    if not token or not token.access_token:
        print("ℹ️ No Salla token for merchant; skipping Salla coupon creation")
        return

    base = (getattr(settings, 'SALLA_API_BASE', '').rstrip('/') or 'https://api.salla.dev/admin/v2')
    # Use only the generic /coupons endpoint (expects type/amount and YYYY-MM-DD dates)
    endpoints = [
        f"{base}/coupons",
    ]

    # Normalized values
    discount_type = "percentage" if coupon.discount_kind == 'percent' else "amount"
    value = float(coupon.amount)
    max_amount = float(coupon.max_discount_amount) if coupon.max_discount_amount is not None else None
    min_cart = float(coupon.min_cart) if coupon.min_cart is not None else None
    free_shipping = bool(coupon.free_shipping)
    exclude_discounted = bool(coupon.exclude_discounted)
    # Format dates as YYYY-MM-DD for /coupons endpoint
    today = timezone.now().date()
    # Start date: required to be today or later; if missing or in the past, set to today
    if coupon.start_date:
        sd = coupon.start_date.date()
        start_date_str = sd.isoformat() if sd >= today else today.isoformat()
    else:
        start_date_str = today.isoformat()

    # Expiry date: required by Salla; if missing, default to 90 days from today
    if coupon.expires_at:
        expiry_date_str = coupon.expires_at.date().isoformat()
    else:
        expiry_date_str = (today + timedelta(days=90)).isoformat()
    usage_limit = coupon.max_uses
    usage_limit_per_customer = coupon.per_customer_limit

    # Payload variants per endpoint family
    legacy_payload = {
        "code": coupon.code,
        "type": discount_type,
        "amount": value,
        "maximum_amount": max_amount,
        "free_shipping": free_shipping,
        # Older naming commonly used
        "exclude_sale_products": exclude_discounted,
        "start_date": start_date_str,
        "expiry_date": expiry_date_str,
        # Usage limits may not be supported on all variants; include if present
        "usage_limit": usage_limit,
        "usage_limit_per_customer": usage_limit_per_customer,
    }
    legacy_payload = {k: v for k, v in legacy_payload.items() if v is not None}

    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_status = None
    last_body = None
    for url in endpoints:
        try:
            send_payload = legacy_payload
            resp = requests.post(url, json=send_payload, headers=headers, timeout=20)
            last_status = resp.status_code
            if resp.status_code in (200, 201):
                data = {}
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                salla_id = (
                    (data.get('data') or {}).get('id')
                    or data.get('id')
                    or (data.get('data') or {}).get('coupon', {}).get('id')
                )
                if salla_id:
                    coupon.salla_coupon_id = str(salla_id)
                    coupon.save(update_fields=["salla_coupon_id"]) 
                    print(f"✅ Created Salla coupon id={salla_id} via {url}")
                    return
            else:
                try:
                    last_body = resp.text
                except Exception:
                    last_body = None
        except requests.exceptions.RequestException as e:
            print(f"🔴 Salla API request error for {url}: {e}")

    print(f"⚠️ Failed to create coupon in Salla. Last status={last_status}, body={last_body}")


def _update_coupon_in_salla(merchant: Merchant, coupon: Coupon) -> None:
    """Best-effort update the coupon in Salla Admin API via PUT request.
    
    Requires coupon.salla_coupon_id to be set (from initial creation).
    """
    if not coupon.salla_coupon_id:
        print("ℹ️ No salla_coupon_id; skipping Salla update")
        return

    token = SallaToken.objects.filter(merchant=merchant).first()
    if not token or not token.access_token:
        print("ℹ️ No Salla token; skipping Salla update")
        return

    base = (getattr(settings, 'SALLA_API_BASE', '').rstrip('/') or 'https://api.salla.dev/admin/v2')
    url = f"{base}/coupons/{coupon.salla_coupon_id}"
    
    today = timezone.now().date()
    # Normalize dates
    if coupon.start_date:
        sd = coupon.start_date.date()
        start_date_str = sd.isoformat() if sd >= today else today.isoformat()
    else:
        start_date_str = today.isoformat()

    if coupon.expires_at:
        expiry_date_str = coupon.expires_at.date().isoformat()
    else:
        expiry_date_str = (today + timedelta(days=90)).isoformat()

    discount_type = "percentage" if coupon.discount_kind == 'percent' else "amount"
    
    payload = {
        "code": coupon.code,
        "type": discount_type,
        "amount": float(coupon.amount),
        "status": "active" if coupon.is_active else "inactive",
        "maximum_amount": float(coupon.max_discount_amount) if coupon.max_discount_amount else None,
        "minimum_amount": float(coupon.min_cart) if coupon.min_cart else None,
        "free_shipping": bool(coupon.free_shipping),
        "exclude_sale_products": bool(coupon.exclude_discounted),
        "start_date": start_date_str,
        "expiry_date": expiry_date_str,
        "usage_limit": coupon.max_uses,
        "usage_limit_per_user": coupon.per_customer_limit,
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        resp = requests.put(url, json=payload, headers=headers, timeout=20)
        if resp.status_code in (200, 201):
            print(f"✅ Updated Salla coupon id={coupon.salla_coupon_id}")
        else:
            print(f"⚠️ Failed to update Salla coupon. Status={resp.status_code}, body={resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"🔴 Salla API update request error: {e}")


def _delete_coupon_in_salla(merchant: Merchant, coupon: Coupon) -> None:
    """Best-effort delete the coupon in Salla Admin API via DELETE request.
    
    Requires coupon.salla_coupon_id to be set (from initial creation).
    """
    if not coupon.salla_coupon_id:
        print("ℹ️ No salla_coupon_id; skipping Salla deletion")
        return

    token = SallaToken.objects.filter(merchant=merchant).first()
    if not token or not token.access_token:
        print("ℹ️ No Salla token; skipping Salla deletion")
        return

    base = (getattr(settings, 'SALLA_API_BASE', '').rstrip('/') or 'https://api.salla.dev/admin/v2')
    url = f"{base}/coupons/{coupon.salla_coupon_id}"

    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/json",
    }

    try:
        resp = requests.delete(url, headers=headers, timeout=20)
        if resp.status_code in (200, 204):
            print(f"✅ Deleted Salla coupon id={coupon.salla_coupon_id}")
        else:
            print(f"⚠️ Failed to delete Salla coupon. Status={resp.status_code}, body={resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"🔴 Salla API delete request error: {e}")


@require_GET
@csrf_exempt
def check_coupon_sync(request, pk: int):
    """Return JSON indicating whether the local coupon exists in Salla.

    Response example:
      {
        "coupon_id": 123,
        "code": "SAVE10",
        "salla_coupon_id": "987654",
        "remote": { "exists": true, "status": 200, "source": "https://.../discounts/coupons/987654" }
      }
    """
    try:
        coupon = get_object_or_404(Coupon, pk=pk)
        merchant = coupon.merchant
    except Exception:
        return JsonResponse({"error": "Coupon not found"}, status=404)

    result = {
        "coupon_id": coupon.id,
        "code": coupon.code,
        "salla_coupon_id": coupon.salla_coupon_id,
        "remote": {"exists": False}
    }

    salla_id = (coupon.salla_coupon_id or "").strip()
    token = SallaToken.objects.filter(merchant=merchant).first()
    if salla_id and token and token.access_token:
        base = (getattr(settings, 'SALLA_API_BASE', '').rstrip('/') or 'https://api.salla.dev/admin/v2')
        candidates = [
            f"{base}/discounts/coupons/{salla_id}",
            f"{base}/discount-coupons/{salla_id}",
            f"{base}/coupons/{salla_id}",
        ]
        headers = {"Authorization": f"Bearer {token.access_token}", "Accept": "application/json"}
        for url in candidates:
            try:
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code == 200:
                    result["remote"] = {"exists": True, "status": r.status_code, "source": url}
                    break
                else:
                    result["remote"] = {"exists": False, "status": r.status_code, "source": url}
            except requests.exceptions.RequestException as e:
                result["remote"] = {"exists": False, "error": str(e), "source": url}

    resp = JsonResponse(result)
    resp['Access-Control-Allow-Origin'] = '*'
    resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp

@csrf_exempt
def resolve_store(request):
    """Resolve store_id by domain for coupons embed.

    Query: GET ?host=<hostname>

    Minimal strategy (dev-friendly):
      - If there is an active SallaToken, return its merchant id.
      - Else if there is exactly one Merchant, return it.
      - Else return 404 (cannot disambiguate).
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        resp = HttpResponse()
        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp['Access-Control-Allow-Headers'] = 'Content-Type'
        resp['Access-Control-Max-Age'] = '86400'
        return resp

    host = request.GET.get('host', '').strip().lower()

    # Try active token first
    token = SallaToken.objects.select_related('merchant').first()
    if token and token.merchant:
        data = {'store_id': token.merchant.salla_merchant_id, 'by': 'token'}
        resp = JsonResponse(data)
        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    # If only one merchant exists, use it (useful for dev environments)
    count = Merchant.objects.count()
    if count == 1:
        m = Merchant.objects.first()
        data = {'store_id': m.salla_merchant_id, 'by': 'single-merchant'}
        resp = JsonResponse(data)
        resp['Access-Control-Allow-Origin'] = '*'
        resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    # No mapping available
    resp = JsonResponse({'error': 'Unable to resolve store for host', 'host': host}, status=404)
    resp['Access-Control-Allow-Origin'] = '*'
    resp['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp['Access-Control-Allow-Headers'] = 'Content-Type'
    return resp


def coupon_embed_js(request):
    """Embed script to display coupon cards on merchant's store"""
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
        response['Access-Control-Max-Age'] = '86400'  # Cache for 24 hours
        return response
    
    if request.method != 'GET':
        return HttpResponse('Method not allowed', status=405)
    
    js = r"""
(function() {
  // === Resolve script element, src & base origin ===
  var SCRIPT_EL = (function(){
    if (document.currentScript) return document.currentScript;
    var s = document.getElementsByTagName('script');
    return s.length ? s[s.length - 1] : null;
  })();
  var SCRIPT_SRC = (SCRIPT_EL && SCRIPT_EL.src) || '';

  // window.__NOMO_BASE__ if set, otherwise extract origin from script URL
  var BASE = (window.__NOMO_BASE__ || '').replace(/\/+$/,'');
  if (!BASE) {
    try {
      var u = new URL(SCRIPT_SRC);
      BASE = u.origin;
    } catch(e) {
      BASE = '';
    }
  }

  function qsFromScript(name, src){
    var m = (src || '').match(new RegExp('[?&]'+name+'=([^&#]+)'));
    return m ? decodeURIComponent(m[1]) : null;
  }

  function isPlaceholder(v){
    return !v || /^\s*\{\{/.test(String(v)) || String(v).toLowerCase()==='null' || String(v).toLowerCase()==='undefined';
  }

  // store_id from query, global, or data-attribute
  var STORE_ID = qsFromScript('store_id', SCRIPT_SRC) || window.__NOMO_STORE_ID__ || (SCRIPT_EL && SCRIPT_EL.getAttribute('data-store-id')) || null;
  
  console.log('Nomo Flow Coupons: Initializing for store', STORE_ID);
  console.log('Nomo Flow Coupons: Using BASE URL', BASE);
  
  function createCouponCard(coupon) {
    var wrap = document.createElement('div');
    wrap.style.cssText = 'position:fixed;bottom:20px;left:20px;z-index:999999;opacity:0;transform:translateY(20px);transition:all 0.3s ease;max-width:350px;';
    
    var card = document.createElement('div');
    card.style.cssText = 'background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);color:white;border-radius:16px;padding:24px;box-shadow:0 20px 60px rgba(102,126,234,0.4);position:relative;overflow:hidden;';
    
    // Decorative circles
    var circle1 = document.createElement('div');
    circle1.style.cssText = 'position:absolute;top:-40px;right:-40px;width:120px;height:120px;background:rgba(255,255,255,0.1);border-radius:50%;';
    card.appendChild(circle1);
    
    var circle2 = document.createElement('div');
    circle2.style.cssText = 'position:absolute;bottom:-30px;left:-30px;width:100px;height:100px;background:rgba(255,255,255,0.1);border-radius:50%;';
    card.appendChild(circle2);
    
    // Close button
    var closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.style.cssText = 'position:absolute;top:12px;left:12px;background:rgba(255,255,255,0.2);border:none;color:white;width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:20px;display:flex;align-items:center;justify-content:center;transition:all 0.2s;';
    closeBtn.onmouseover = function() { this.style.background = 'rgba(255,255,255,0.3)'; };
    closeBtn.onmouseout = function() { this.style.background = 'rgba(255,255,255,0.2)'; };
    closeBtn.onclick = function() {
      wrap.style.opacity = '0';
      wrap.style.transform = 'translateY(20px)';
      setTimeout(function() { wrap.remove(); }, 300);
    };
    card.appendChild(closeBtn);
    
    // Content
    var content = document.createElement('div');
    content.style.cssText = 'position:relative;z-index:1;';
    
    // Discount badge
    var badge = document.createElement('div');
    var discountText = coupon.discount_kind === 'percent' ? coupon.amount + '% OFF!' : coupon.amount + ' SAR OFF!';
    badge.textContent = discountText;
    badge.style.cssText = 'font-size:32px;font-weight:800;margin-bottom:8px;text-shadow:0 2px 10px rgba(0,0,0,0.2);';
    content.appendChild(badge);
    
    // Title
    var title = document.createElement('div');
    title.textContent = 'Limited Time Discount Coupon!';
    title.style.cssText = 'font-size:16px;font-weight:600;margin-bottom:16px;opacity:0.95;';
    content.appendChild(title);
    
    // Coupon code container
    var codeContainer = document.createElement('div');
    codeContainer.style.cssText = 'background:rgba(255,255,255,0.2);border-radius:12px;padding:12px;margin-bottom:12px;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(10px);';
    
    var code = document.createElement('div');
    code.textContent = coupon.code;
    code.style.cssText = 'font-family:monospace;font-size:20px;font-weight:700;letter-spacing:2px;text-align:center;';
    codeContainer.appendChild(code);
    
    content.appendChild(codeContainer);
    
    // Copy button
    var copyBtn = document.createElement('button');
    copyBtn.textContent = 'Copy Discount Code';
    copyBtn.style.cssText = 'width:100%;background:white;color:#667eea;border:none;padding:12px;border-radius:10px;font-weight:700;font-size:14px;cursor:pointer;transition:all 0.2s;box-shadow:0 4px 15px rgba(0,0,0,0.2);';
    copyBtn.onmouseover = function() { 
      this.style.transform = 'translateY(-2px)';
      this.style.boxShadow = '0 6px 20px rgba(0,0,0,0.3)';
    };
    copyBtn.onmouseout = function() { 
      this.style.transform = 'translateY(0)';
      this.style.boxShadow = '0 4px 15px rgba(0,0,0,0.2)';
    };
    copyBtn.onclick = function() {
      // Copy to clipboard
      if (navigator.clipboard) {
        navigator.clipboard.writeText(coupon.code).then(function() {
          copyBtn.textContent = '✓ Code Copied!';
          copyBtn.style.background = '#10b981';
          copyBtn.style.color = 'white';
          setTimeout(function() {
            copyBtn.textContent = 'Copy Discount Code';
            copyBtn.style.background = 'white';
            copyBtn.style.color = '#667eea';
          }, 2000);
        });
      } else {
        // Fallback for older browsers
        var textArea = document.createElement('textarea');
        textArea.value = coupon.code;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
          document.execCommand('copy');
          copyBtn.textContent = '✓ Code Copied!';
          copyBtn.style.background = '#10b981';
          copyBtn.style.color = 'white';
          setTimeout(function() {
            copyBtn.textContent = 'Copy Discount Code';
            copyBtn.style.background = 'white';
            copyBtn.style.color = '#667eea';
          }, 2000);
        } catch(err) {
          console.error('Failed to copy:', err);
        }
        document.body.removeChild(textArea);
      }
    };
    content.appendChild(copyBtn);
    
    // Additional info
    if (coupon.min_cart || coupon.free_shipping) {
      var info = document.createElement('div');
      info.style.cssText = 'margin-top:12px;font-size:12px;opacity:0.9;text-align:center;';
      var infoText = [];
      if (coupon.min_cart) infoText.push('Min. ' + coupon.min_cart + ' SAR');
      if (coupon.free_shipping) infoText.push('Free Shipping');
      info.textContent = infoText.join(' • ');
      content.appendChild(info);
    }
    
    card.appendChild(content);
    wrap.appendChild(card);
    document.body.appendChild(wrap);
    
    // Animate in
    setTimeout(function() {
      wrap.style.opacity = '1';
      wrap.style.transform = 'translateY(0)';
    }, 100);
    
    console.log('Nomo Flow Coupons: Card displayed for coupon', coupon.code);
  }
  
  function fetchAndDisplayCoupons() {
    if (!BASE || !STORE_ID) {
      console.error('Nomo Flow Coupons: Missing BASE URL or STORE_ID');
      return;
    }
    
    var url = BASE + '/coupons/feed/?store_id=' + encodeURIComponent(STORE_ID);
    
    console.log('Nomo Flow Coupons: Fetching from', url);
    
    fetch(url, {
      headers: { 'ngrok-skip-browser-warning': 'true' }
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
      console.log('Nomo Flow Coupons: Received', data.coupons.length, 'coupons');
      
      if (data.coupons && data.coupons.length > 0) {
        // Show first active coupon
        createCouponCard(data.coupons[0]);
      } else {
        console.log('Nomo Flow Coupons: No active coupons');
      }
    })
    .catch(function(error) {
      console.error('Nomo Flow Coupons: Error', error);
    });
  }
  
  // === Resolve STORE_ID if missing/placeholder without relying on onReady ===
  function tryGetFromSalla(){
    try {
      if (window.salla && typeof window.salla.config?.get === 'function') {
        return window.salla.config.get('store.id') || window.salla.config.get('merchant.id') || null;
      }
    } catch(e) {}
    try {
      if (window.Salla && window.Salla.store && window.Salla.store.id) {
        return window.Salla.store.id;
      }
    } catch(e) {}
    return null;
  }

  function start(){
    if (isPlaceholder(STORE_ID)) {
      var fromSalla = tryGetFromSalla();
      if (fromSalla) STORE_ID = fromSalla;
    }
    if (isPlaceholder(STORE_ID)) {
      var attempts = 0;
      var timer = setInterval(function(){
        attempts += 1;
        var sid = tryGetFromSalla();
        if (sid) {
          clearInterval(timer);
          STORE_ID = sid;
          fetchAndDisplayCoupons();
        } else if (attempts >= 10) {
          clearInterval(timer);
          // Final fallback: resolve by domain
          var url = BASE + '/coupon/resolve-store?host=' + encodeURIComponent(location.hostname);
          fetch(url, { headers: { 'ngrok-skip-browser-warning': 'true' }})
            .then(function(r){ return r.ok ? r.json() : Promise.reject(r); })
            .then(function(d){
              if (d && d.store_id) {
                STORE_ID = d.store_id;
                fetchAndDisplayCoupons();
              } else {
                console.warn('Nomo Flow Coupons: resolve-store returned no store_id');
              }
            })
            .catch(function(){ console.warn('Nomo Flow Coupons: Could not resolve STORE_ID'); });
        }
      }, 300);
    } else {
      fetchAndDisplayCoupons();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
"""
    
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    return response
