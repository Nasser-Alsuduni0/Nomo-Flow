from copy import deepcopy
from decimal import Decimal
from typing import Optional

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.timesince import timesince
from django.db.models import Count, Sum
from django.core.paginator import Paginator

from core.utils import get_current_merchant
from core.models import Merchant, EmailSubscriber, Attribution

from .models import MerchantFeature, Feature
from .forms import EmailSubscriberForm

import json


FEATURE_DEFAULTS = {
    "email_collector": {
        "title": "Email Collector",
        "description": "Collect email subscribers from your store",
    },
    "recent_purchases": {
        "title": "Purchase Display",
        "description": "Show recent purchases as social proof popups",
    },
    "live_counter": {
        "title": "Live View Counter",
        "description": "Show real-time visitor count on your store",
    },
}


PURCHASE_DISPLAY_DEFAULT_SETTINGS = {
    "display_duration_ms": 6000,
    "delay_between_ms": 4000,
    "max_items": 12,
    "loop": True,
    "position": "bottom-left",
    "show_amount": True,
    "show_order_reference": True,
    "show_coupon": True,
    "lookback_hours": 72,
    "animation": "slide-up",
}


def _get_feature_defaults(feature_key: str) -> dict:
    defaults = FEATURE_DEFAULTS.get(feature_key, None)
    if defaults is None:
        human_title = feature_key.replace("_", " ").title()
        return {"title": human_title, "description": ""}
    return defaults


def _ensure_feature(feature_key: str) -> Feature:
    defaults = _get_feature_defaults(feature_key)
    feature, _ = Feature.objects.get_or_create(key=feature_key, defaults=defaults)
    return feature


def _ensure_merchant_feature(merchant: Merchant, feature: Feature, *, default_settings: Optional[dict] = None) -> MerchantFeature:
    defaults: dict[str, object] = {"is_enabled": False}
    if default_settings is not None:
        defaults["settings_json"] = deepcopy(default_settings)

    merchant_feature, created = MerchantFeature.objects.get_or_create(
        merchant=merchant,
        feature=feature,
        defaults=defaults,
    )

    if default_settings is not None and not merchant_feature.settings_json:
        merchant_feature.settings_json = deepcopy(default_settings)
        merchant_feature.save(update_fields=["settings_json"])

    if created and default_settings is not None and merchant_feature.settings_json != default_settings:
        merchant_feature.settings_json = deepcopy(default_settings)
        merchant_feature.save(update_fields=["settings_json"])

    return merchant_feature


def _format_timesince(dt):
    if not dt:
        return ""
    delta = timesince(dt, timezone.now())
    if not delta or delta.startswith("0 minutes"):
        return "moments ago"
    # Only keep the first component (e.g., "2 hours").
    concise = delta.split(",")[0].strip()
    return f"{concise} ago"


def _cors_preflight_response() -> HttpResponse:
    response = HttpResponse()
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, ngrok-skip-browser-warning"
    response["Access-Control-Max-Age"] = "86400"
    return response


def _json_with_cors(payload: dict, *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, ngrok-skip-browser-warning"
    response["Access-Control-Max-Age"] = "86400"
    return response


def email_collector_page(request):
    """Dashboard page for email collector"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    # Get or create the email_collector feature and merchant feature
    feature = _ensure_feature("email_collector")
    merchant_feature = _ensure_merchant_feature(merchant, feature)
    
    # Get all subscribers for this merchant
    subscribers = EmailSubscriber.objects.filter(merchant=merchant).order_by('-subscribed_at')
    
    # Pagination
    paginator = Paginator(subscribers, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Stats
    total_subscribers = subscribers.count()
    active_subscribers = subscribers.filter(consent=True, unsubscribed_at__isnull=True).count()
    unsubscribed = subscribers.filter(unsubscribed_at__isnull=False).count()
    
    # Recent subscribers (last 7 days)
    recent_date = timezone.now() - timezone.timedelta(days=7)
    recent_count = subscribers.filter(subscribed_at__gte=recent_date).count()
    
    context = {
        'subscribers': page_obj,
        'total_subscribers': total_subscribers,
        'active_subscribers': active_subscribers,
        'unsubscribed': unsubscribed,
        'recent_count': recent_count,
        'merchant': merchant,
        'is_enabled': merchant_feature.is_enabled,
    }
    
    return render(request, 'features/email_collector.html', context)


def _check_feature_ready(merchant, feature_key: str) -> tuple[bool, str]:
    """
    Check if a feature is ready to be enabled (has required setup).
    Returns (is_ready, error_message)
    """
    if feature_key == 'notifications':
        # Check if merchant has at least one PopupNotification
        from notifications.models import PopupNotification
        if not PopupNotification.objects.filter(merchant=merchant).exists():
            return False, "Please create at least one notification first. Go to Settings to create your first notification."
    
    elif feature_key == 'coupons':
        # Check if merchant has at least one Coupon
        from coupons.models import Coupon
        if not Coupon.objects.filter(merchant=merchant).exists():
            return False, "Please create at least one discount coupon first. Go to Settings to create your first coupon."
    
    # Other features (email_collector, live_counter, recent_purchases) don't require setup
    return True, ""


@require_http_methods(["POST"])
def toggle_feature(request):
    """Toggle a merchant feature on/off (defaults to email collector)."""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'success': False, 'message': 'No merchant selected'}, status=400)
    
    try:
        data = json.loads(request.body)
        enabled = data.get('enabled', False)
        feature_key = data.get('feature', 'email_collector')

        # If trying to enable, check if feature is ready
        if enabled:
            is_ready, error_message = _check_feature_ready(merchant, feature_key)
            if not is_ready:
                # Get settings URL for the feature
                settings_urls = {
                    'notifications': '/dashboard/notifications/',
                    'coupons': '/dashboard/discount-coupons/',
                }
                settings_url = settings_urls.get(feature_key, '/dashboard/features/')
                
                return JsonResponse({
                    'success': False,
                    'message': error_message,
                    'requires_setup': True,
                    'settings_url': settings_url
                }, status=400)

        feature = _ensure_feature(feature_key)

        default_settings = PURCHASE_DISPLAY_DEFAULT_SETTINGS if feature_key == 'recent_purchases' else None
        merchant_feature = _ensure_merchant_feature(
            merchant,
            feature,
            default_settings=default_settings,
        )

        merchant_feature.is_enabled = enabled
        merchant_feature.save(update_fields=['is_enabled'])

        feature_title = feature.title or feature_key.replace('_', ' ').title()
        
        return JsonResponse({
            'success': True,
            'is_enabled': enabled,
            'message': f'{feature_title} {"enabled" if enabled else "disabled"} successfully'
        })
    except Exception as e:
        print(f"Error in toggle_feature: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def subscribe_email(request):
    """API endpoint for email subscription (called from storefront embed)"""
    try:
        # Parse JSON body
        data = json.loads(request.body)
        email = data.get('email', '').strip()
        name = data.get('name', '').strip()
        store_id = data.get('store_id')
        
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'}, status=400)
        
        if not store_id:
            return JsonResponse({'success': False, 'message': 'Store ID is required'}, status=400)
        
        # Get merchant
        try:
            merchant = Merchant.objects.get(salla_merchant_id=store_id)
        except Merchant.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Store not found'}, status=404)
        
        # Check if email already exists
        subscriber, created = EmailSubscriber.objects.get_or_create(
            merchant=merchant,
            email=email,
            defaults={
                'name': name,
                'source': 'popup',
                'consent': True,
                'subscribed_at': timezone.now(),
            }
        )
        
        if not created:
            # Email already exists - update if unsubscribed
            if subscriber.unsubscribed_at:
                subscriber.consent = True
                subscriber.subscribed_at = timezone.now()
                subscriber.unsubscribed_at = None
                if name:
                    subscriber.name = name
                subscriber.save()
                message = 'Welcome back! You have been re-subscribed.'
            else:
                message = 'You are already subscribed!'
        else:
            message = 'Thank you for subscribing!'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'created': created
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in subscribe_email: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)


@require_http_methods(["POST"])
def unsubscribe_email(request, pk):
    """Unsubscribe an email"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'success': False, 'message': 'No merchant selected'}, status=400)
    
    subscriber = get_object_or_404(EmailSubscriber, pk=pk, merchant=merchant)
    subscriber.consent = False
    subscriber.unsubscribed_at = timezone.now()
    subscriber.save()
    
    return JsonResponse({'success': True, 'message': 'Email unsubscribed successfully'})


@require_http_methods(["POST"])
def delete_subscriber(request, pk):
    """Delete a subscriber"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'success': False, 'message': 'No merchant selected'}, status=400)
    
    subscriber = get_object_or_404(EmailSubscriber, pk=pk, merchant=merchant)
    subscriber.delete()
    
    return JsonResponse({'success': True, 'message': 'Subscriber deleted successfully'})


@require_http_methods(["GET"])
def export_subscribers(request):
    """Export subscribers as CSV"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    subscribers = EmailSubscriber.objects.filter(merchant=merchant, consent=True, unsubscribed_at__isnull=True).order_by('-subscribed_at')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="subscribers_{merchant.salla_merchant_id}.csv"'
    
    import csv
    writer = csv.writer(response)
    writer.writerow(['Email', 'Name', 'Source', 'Subscribed At', 'IP Address'])
    
    for sub in subscribers:
        writer.writerow([
            sub.email,
            sub.name or '',
            sub.source or 'popup',
            sub.subscribed_at.strftime('%Y-%m-%d %H:%M:%S'),
            ''  # IP address not stored in core model
        ])
    
    return response


def email_embed_js(request):
    """Generate the email collector embed JavaScript"""
    store_id = request.GET.get('store_id', '')
    
    # Force HTTPS for external requests (ngrok supports HTTPS)
    base_url = f"https://{request.get_host()}"
    
    js_code = f"""
(function() {{
    'use strict';
    
    // Prevent double-loading
    if (window.__NOMO_EMAIL_EMBED_LOADED__) {{
        console.log('[Nomo Email Collector] Already loaded, skipping');
        return;
    }}
    window.__NOMO_EMAIL_EMBED_LOADED__ = true;
    
    const BASE_URL = '{base_url}';
    const STORE_ID = '{store_id}';
    
    // First, check if the feature is enabled for this store
    fetch(BASE_URL + '/features/is-enabled/?store_id=' + encodeURIComponent(STORE_ID), {{
        headers: {{
            'ngrok-skip-browser-warning': 'true'
        }}
    }})
        .then(response => {{
            if (!response.ok) {{
                console.error('[Nomo Email Collector] API error:', response.status);
                return {{ enabled: false }};
            }}
            return response.json();
        }})
        .then(data => {{
            if (!data.enabled) {{
                console.log('[Nomo Email Collector] Feature is disabled for this store');
                return;
            }}
            
            // Check if user has already subscribed (localStorage)
            const hasSubscribed = localStorage.getItem('nomo_email_subscribed_' + STORE_ID);
            if (hasSubscribed) {{
                console.log('[Nomo Email Collector] User already subscribed');
                return;
            }}
            
            // Check if popup was already shown in this session
            const sessionKey = 'nomo_email_popup_shown_' + STORE_ID;
            if (sessionStorage.getItem(sessionKey)) {{
                console.log('[Nomo Email Collector] Popup already shown in this session');
                return;
            }}
            
            // Initialize the popup
            initEmailPopup();
        }})
        .catch(error => {{
            console.error('[Nomo Email Collector] Error checking feature status:', error);
        }});
    
    function initEmailPopup() {{
    const sessionKey = 'nomo_email_popup_shown_' + STORE_ID;
    
    // Create popup HTML
    function createPopup() {{
        const popup = document.createElement('div');
        popup.id = 'nomo-email-popup';
        popup.setAttribute('data-nomo-email-popup', 'true');
        popup.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            z-index: 999999;
            max-width: 400px;
            width: 90%;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            animation: nomoSlideIn 0.4s ease-out;
            direction: ltr;
            text-align: left;
        `;
        
        popup.innerHTML = `
            <style>
                @keyframes nomoSlideIn {{
                    from {{
                        opacity: 0;
                        transform: translate(-50%, -45%);
                    }}
                    to {{
                        opacity: 1;
                        transform: translate(-50%, -50%);
                    }}
                }}
                #nomo-email-popup h3 {{
                    margin: 0 0 10px 0;
                    font-size: 24px;
                    font-weight: bold;
                }}
                #nomo-email-popup p {{
                    margin: 0 0 20px 0;
                    font-size: 14px;
                    opacity: 0.95;
                }}
                #nomo-email-popup input {{
                    width: 100%;
                    padding: 12px;
                    margin-bottom: 10px;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    box-sizing: border-box;
                    direction: ltr;
                    color: #1e293b;
                    background: white;
                }}
                #nomo-email-popup input::placeholder {{
                    color: #94a3b8;
                }}
                #nomo-email-popup button {{
                    width: 100%;
                    padding: 12px;
                    border: none;
                    border-radius: 8px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: all 0.3s;
                }}
                #nomo-email-submit {{
                    background: white;
                    color: #667eea;
                    margin-bottom: 10px;
                }}
                #nomo-email-submit:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                }}
                #nomo-email-close {{
                    background: transparent;
                    color: white;
                    text-decoration: underline;
                }}
                #nomo-email-overlay {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.5);
                    z-index: 999998;
                    animation: nomoFadeIn 0.3s ease-out;
                }}
                @keyframes nomoFadeIn {{
                    from {{ opacity: 0; }}
                    to {{ opacity: 1; }}
                }}
                .nomo-success-message {{
                    background: #10b981;
                    color: white;
                    padding: 12px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 10px;
                }}
                .nomo-error-message {{
                    background: #ef4444;
                    color: white;
                    padding: 12px;
                    border-radius: 8px;
                    text-align: center;
                    margin-bottom: 10px;
                }}
            </style>
            <div id="nomo-email-message"></div>
            <h3>Subscribe to Our Newsletter</h3>
            <p>Get the latest offers and updates delivered directly to your inbox</p>
            <input type="email" id="nomo-email-input" placeholder="Your email address" required>
            <input type="text" id="nomo-name-input" placeholder="Your name (optional)">
            <button id="nomo-email-submit">Subscribe Now</button>
            <button id="nomo-email-close">No, Thanks</button>
        `;
        
        return popup;
    }}
    
    // Create overlay
    function createOverlay() {{
        const overlay = document.createElement('div');
        overlay.id = 'nomo-email-overlay';
        return overlay;
    }}
    
    // Show popup after delay
    function showPopup() {{
        // Remove any existing popups
        const existing = document.querySelector('[data-nomo-email-popup]');
        if (existing) {{
            existing.remove();
        }}
        
        const overlay = createOverlay();
        const popup = createPopup();
        
        document.body.appendChild(overlay);
        document.body.appendChild(popup);
        
        // Mark as shown in session
        sessionStorage.setItem(sessionKey, 'true');
        
        // Close button
        document.getElementById('nomo-email-close').addEventListener('click', function() {{
            popup.remove();
            overlay.remove();
        }});
        
        // Close on overlay click
        overlay.addEventListener('click', function() {{
            popup.remove();
            overlay.remove();
        }});
        
        // Submit form
        document.getElementById('nomo-email-submit').addEventListener('click', function() {{
            const email = document.getElementById('nomo-email-input').value.trim();
            const name = document.getElementById('nomo-name-input').value.trim();
            const messageDiv = document.getElementById('nomo-email-message');
            
            if (!email) {{
                messageDiv.innerHTML = '<div class="nomo-error-message">Please enter your email address</div>';
                return;
            }}
            
            // Basic email validation
            const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
            if (!emailRegex.test(email)) {{
                messageDiv.innerHTML = '<div class="nomo-error-message">Please enter a valid email address</div>';
                return;
            }}
            
            // Disable button
            const submitBtn = document.getElementById('nomo-email-submit');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Subscribing...';
            
            // Send to server
            fetch(BASE_URL + '/features/subscribe/', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                }},
                body: JSON.stringify({{
                    email: email,
                    name: name,
                    store_id: STORE_ID
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    messageDiv.innerHTML = '<div class="nomo-success-message">' + data.message + '</div>';
                    localStorage.setItem('nomo_email_subscribed_' + STORE_ID, 'true');
                    
                    // Close popup after 2 seconds
                    setTimeout(function() {{
                        popup.remove();
                        overlay.remove();
                    }}, 2000);
                }} else {{
                    messageDiv.innerHTML = '<div class="nomo-error-message">' + data.message + '</div>';
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Subscribe Now';
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                messageDiv.innerHTML = '<div class="nomo-error-message">An error occurred, please try again</div>';
                submitBtn.disabled = false;
                submitBtn.textContent = 'Subscribe Now';
            }});
        }});
        
        // Enter key on email input
        document.getElementById('nomo-email-input').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                document.getElementById('nomo-email-submit').click();
            }}
        }});
    }}
    
    // Show popup after 5 seconds
    setTimeout(showPopup, 5000);
    }}
    
}})();
""".strip()
    
    return HttpResponse(js_code, content_type='application/javascript')


@require_http_methods(["GET"])
def is_feature_enabled(request):
    """Check if a feature is enabled for a store"""
    store_id = request.GET.get('store_id')
    feature_key = request.GET.get('feature', 'email_collector')
    
    if not store_id:
        return _json_with_cors({'enabled': False, 'message': 'Store ID required'}, status=400)
    
    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
    except Merchant.DoesNotExist:
        return _json_with_cors({'enabled': False, 'message': 'Store not found'}, status=404)
        
    feature = Feature.objects.filter(key=feature_key).first()
    if not feature:
        return _json_with_cors({'enabled': False})

    merchant_feature = MerchantFeature.objects.filter(
        merchant=merchant,
        feature=feature
    ).first()

    if not merchant_feature:
        return _json_with_cors({'enabled': False})

    payload = {'enabled': merchant_feature.is_enabled}
    if merchant_feature.settings_json:
        payload['settings'] = merchant_feature.settings_json

    return _json_with_cors(payload)


def purchase_display_page(request):
    """Dashboard page for purchase display social proof"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')

    feature = _ensure_feature('recent_purchases')
    merchant_feature = _ensure_merchant_feature(
        merchant,
        feature,
        default_settings=PURCHASE_DISPLAY_DEFAULT_SETTINGS,
    )

    settings = merchant_feature.settings_json or deepcopy(PURCHASE_DISPLAY_DEFAULT_SETTINGS)
    if not isinstance(settings, dict):
        settings = deepcopy(PURCHASE_DISPLAY_DEFAULT_SETTINGS)

    settings_items = [
        {
            'key': key,
            'label': key.replace('_', ' ').title(),
            'value': value,
        }
        for key, value in settings.items()
    ]

    orders_qs = Attribution.objects.filter(merchant=merchant).order_by('-occurred_at')

    total_orders = orders_qs.count()
    total_revenue = orders_qs.aggregate(total=Sum('revenue_sar'))['total'] or Decimal('0')

    now = timezone.now()
    last_24h = now - timezone.timedelta(hours=24)
    last_7_days = now - timezone.timedelta(days=7)

    orders_last_24h = orders_qs.filter(occurred_at__gte=last_24h).count()
    orders_last_7_days = orders_qs.filter(occurred_at__gte=last_7_days).count()

    latest_order = orders_qs.first()
    latest_order_amount = latest_order.revenue_sar if latest_order else None
    latest_order_time = latest_order.occurred_at if latest_order else None

    recent_orders = []
    for attribution in orders_qs[:20]:
        recent_orders.append({
            'order_id': attribution.salla_order_id,
            'order_display': f"Order #{attribution.salla_order_id[-4:]}" if attribution.salla_order_id else 'Order',
            'revenue': attribution.revenue_sar,
            'ago': _format_timesince(attribution.occurred_at),
            'occurred_at': attribution.occurred_at,
            'used_coupon': attribution.used_coupon_code,
        })

    embed_url = request.build_absolute_uri(reverse('features:purchase_display_embed_js'))
    feed_url = request.build_absolute_uri(reverse('features:purchase_display_feed'))
    base_origin = request.build_absolute_uri('/').rstrip('/')

    context = {
        'merchant': merchant,
        'feature': feature,
        'merchant_feature': merchant_feature,
        'settings': settings,
        'settings_items': settings_items,
        'is_enabled': merchant_feature.is_enabled,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'orders_last_24h': orders_last_24h,
        'orders_last_7_days': orders_last_7_days,
        'latest_order_amount': latest_order_amount,
        'latest_order_time': latest_order_time,
        'latest_order_time_ago': _format_timesince(latest_order_time) if latest_order_time else None,
        'recent_orders': recent_orders,
        'embed_url': embed_url,
        'feed_url': feed_url,
    }

    return render(request, 'features/purchase_display.html', context)


@require_http_methods(["GET", "OPTIONS"])
def purchase_display_feed(request):
    """Public feed of recent purchases for embed widget"""
    if request.method == 'OPTIONS':
        return _cors_preflight_response()

    store_id = request.GET.get('store_id')
    if not store_id:
        return _json_with_cors(
            {'enabled': False, 'items': [], 'message': 'Store ID required'},
            status=400,
        )

    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
    except Merchant.DoesNotExist:
        return _json_with_cors(
            {'enabled': False, 'items': [], 'message': 'Store not found'},
            status=404,
        )

    feature = Feature.objects.filter(key='recent_purchases').first()
    if not feature:
        return _json_with_cors({'enabled': False, 'items': []})

    merchant_feature = MerchantFeature.objects.filter(merchant=merchant, feature=feature).first()
    if not merchant_feature or not merchant_feature.is_enabled:
        return _json_with_cors({'enabled': False, 'items': []})

    settings = merchant_feature.settings_json or deepcopy(PURCHASE_DISPLAY_DEFAULT_SETTINGS)
    if not isinstance(settings, dict):
        settings = deepcopy(PURCHASE_DISPLAY_DEFAULT_SETTINGS)

    max_items = settings.get('max_items', 12)
    try:
        limit_param = request.GET.get('limit')
        if limit_param is not None:
            max_items = max(1, min(int(limit_param), max_items))
    except (TypeError, ValueError):
        max_items = settings.get('max_items', 12)

    lookback_hours = settings.get('lookback_hours', 72)
    try:
        hours_param = request.GET.get('hours')
        if hours_param is not None:
            lookback_hours = max(1, min(int(hours_param), lookback_hours))
    except (TypeError, ValueError):
        lookback_hours = settings.get('lookback_hours', 72)

    purchases_qs = Attribution.objects.filter(merchant=merchant)
    if lookback_hours:
        cutoff = timezone.now() - timezone.timedelta(hours=lookback_hours)
        purchases_qs = purchases_qs.filter(occurred_at__gte=cutoff)

    purchases_qs = purchases_qs.order_by('-occurred_at')[:max_items]

    items = []
    for attribution in purchases_qs:
        amount = float(attribution.revenue_sar) if attribution.revenue_sar is not None else None
        order_id = attribution.salla_order_id or ''
        if order_id and len(order_id) > 6:
            order_display = f"Order #{order_id[-4:]}"
        elif order_id:
            order_display = f"Order #{order_id}"
        else:
            order_display = "Recent order"

        items.append({
            'order_id': order_id,
            'order_display': order_display,
            'customer_name': attribution.customer_name or None,
            'product_name': attribution.product_name or None,
            'amount': amount,
            'currency': 'SAR',
            'ago': _format_timesince(attribution.occurred_at),
            'occurred_at': attribution.occurred_at.isoformat() if attribution.occurred_at else None,
            'used_coupon': attribution.used_coupon_code,
        })

    settings_payload = deepcopy(settings)

    return _json_with_cors({
        'enabled': True,
        'items': items,
        'settings': settings_payload,
        'count': len(items),
    })


@require_http_methods(["GET", "OPTIONS"])
def purchase_display_embed_js(request):
    """Embeddable JavaScript for purchase display popups"""
    if request.method == 'OPTIONS':
        return _cors_preflight_response()

    store_id = request.GET.get('store_id', '')
    base_url = f"https://{request.get_host()}"

    defaults_json = json.dumps(PURCHASE_DISPLAY_DEFAULT_SETTINGS)
    base_url_json = json.dumps(base_url)
    store_id_json = json.dumps(store_id or "")

    script_template = r"""
(function() {
    'use strict';

    if (window.__NOMO_PURCHASE_DISPLAY_LOADED__) {
        console.log('[Nomo Purchase Display] Already loaded, skipping');
        return;
    }
    window.__NOMO_PURCHASE_DISPLAY_LOADED__ = true;

    var DEFAULT_SETTINGS = __DEFAULT_SETTINGS__;

    var SCRIPT_EL = (function() {
        if (document.currentScript) return document.currentScript;
        var scripts = document.getElementsByTagName('script');
        return scripts.length ? scripts[scripts.length - 1] : null;
    })();
    var SCRIPT_SRC = (SCRIPT_EL && SCRIPT_EL.src) || '';

    var BASE_URL = (window._NOMO_BASE_ || '').replace(/\/+$/, '');
    if (!BASE_URL) {
        try {
            var parsed = new URL(SCRIPT_SRC);
            BASE_URL = parsed.origin;
        } catch (err) {
            BASE_URL = __BASE_URL__;
        }
    }

    var STORE_ID = __STORE_ID__ || window._NOMO_STORE_ID_ || (SCRIPT_EL && SCRIPT_EL.getAttribute('data-store-id')) || null;

    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    function fetchFeatureStatus() {
        var url = BASE_URL + '/features/is-enabled/?feature=recent_purchases&store_id=' + encodeURIComponent(STORE_ID || '');
        return fetch(url, {
            method: 'GET',
            headers: { 'ngrok-skip-browser-warning': 'true' }
        }).then(function(response) {
            if (!response.ok) {
                console.warn('[Nomo Purchase Display] Feature status error', response.status);
                return { enabled: false };
            }
            return response.json();
        }).catch(function(err) {
            console.error('[Nomo Purchase Display] Failed to read feature status', err);
            return { enabled: false };
        });
    }

    function fetchFeed(settings) {
        var url = BASE_URL + '/features/purchase-display/feed/?store_id=' + encodeURIComponent(STORE_ID || '');
        if (settings && settings.max_items) {
            url += '&limit=' + encodeURIComponent(settings.max_items);
        }
        return fetch(url, {
            method: 'GET',
            headers: { 'ngrok-skip-browser-warning': 'true', 'Accept': 'application/json' }
        }).then(function(response) {
            if (!response.ok) {
                console.warn('[Nomo Purchase Display] Feed error', response.status);
                return { enabled: false, items: [] };
            }
            return response.json();
        }).catch(function(err) {
            console.error('[Nomo Purchase Display] Unable to load feed', err);
            return { enabled: false, items: [] };
        });
    }

    function applyPosition(el, position) {
        var pos = (position || 'bottom-left').toLowerCase();
        el.style.top = '';
        el.style.bottom = '';
        el.style.left = '';
        el.style.right = '';
        el.style.transform = '';

        if (pos === 'top-left') {
            el.style.top = '20px';
            el.style.left = '20px';
        } else if (pos === 'top-right') {
            el.style.top = '20px';
            el.style.right = '20px';
        } else if (pos === 'bottom-right') {
            el.style.bottom = '20px';
            el.style.right = '20px';
        } else if (pos === 'bottom-center') {
            el.style.bottom = '20px';
            el.style.left = '50%';
            el.style.transform = 'translateX(-50%)';
        } else if (pos === 'top-center') {
            el.style.top = '20px';
            el.style.left = '50%';
            el.style.transform = 'translateX(-50%)';
        } else {
            el.style.bottom = '20px';
            el.style.left = '20px';
        }
    }

    function formatAmount(amount, currency) {
        if (typeof amount !== 'number' || isNaN(amount)) return '';
        try {
            return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: currency || 'SAR', maximumFractionDigits: 0 }).format(amount);
        } catch (err) {
            return amount.toFixed(0) + ' ' + (currency || 'SAR');
        }
    }

    // Single timer reference to prevent conflicts
    var loopTimer = null;
    var currentPopup = null;
    var isAnimating = false;

    function hidePopup(callback) {
        if (!currentPopup || isAnimating) {
            if (callback) callback();
            return;
        }
        isAnimating = true;
        currentPopup.style.opacity = '0';
        currentPopup.style.transform = 'translateY(20px)';
        
        setTimeout(function() {
            if (currentPopup) {
                currentPopup.remove();
                currentPopup = null;
            }
            isAnimating = false;
            if (callback) callback();
        }, 400);
    }

    function showPurchase(item, settings, onComplete) {
        // Wait for any existing animation to complete
        if (isAnimating) {
            setTimeout(function() { showPurchase(item, settings, onComplete); }, 100);
            return;
        }

        // Remove existing popup first
        if (currentPopup) {
            currentPopup.remove();
            currentPopup = null;
        }

        var wrapper = document.createElement('div');
        wrapper.setAttribute('data-nomo-purchase-popup', '1');
        wrapper.style.cssText = 'position:fixed;z-index:999999;opacity:0;pointer-events:none;transition:all 0.4s cubic-bezier(0.4, 0, 0.2, 1);transform:translateY(20px);';

        applyPosition(wrapper, settings.position);

        // Card with purple gradient matching email popup
        var card = document.createElement('div');
        card.style.cssText = 'min-width:300px;max-width:380px;background:linear-gradient(135deg, #667eea 0%, #764ba2 100%);color:#ffffff;border-radius:15px;padding:20px 24px;box-shadow:0 10px 40px rgba(102,126,234,0.4);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:row;gap:16px;align-items:center;position:relative;overflow:hidden;';

        // Shopping bag icon
        var iconBox = document.createElement('div');
        iconBox.style.cssText = 'width:50px;height:50px;border-radius:12px;background:rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;flex-shrink:0;';
        iconBox.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>';
        card.appendChild(iconBox);

        // Content
        var content = document.createElement('div');
        content.style.cssText = 'flex:1;min-width:0;';

        // Customer name + action
        var headline = document.createElement('div');
        headline.style.cssText = 'font-weight:700;font-size:15px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
        var customerName = item.customer_name || 'Someone';
        headline.textContent = customerName + ' just bought';
        content.appendChild(headline);

        // Product name
        var productLine = document.createElement('div');
        productLine.style.cssText = 'font-size:14px;font-weight:500;opacity:0.95;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
        productLine.textContent = item.product_name || 'a product';
        content.appendChild(productLine);

        // Price and time
        var metaLine = document.createElement('div');
        metaLine.style.cssText = 'font-size:13px;opacity:0.85;display:flex;gap:8px;align-items:center;';
        
        var priceSpan = document.createElement('span');
        priceSpan.style.cssText = 'background:rgba(255,255,255,0.2);padding:2px 8px;border-radius:10px;font-weight:600;';
        priceSpan.textContent = item.amount ? formatAmount(item.amount, item.currency) : '';
        
        var timeSpan = document.createElement('span');
        timeSpan.textContent = item.ago || 'Just now';
        
        if (item.amount) metaLine.appendChild(priceSpan);
        metaLine.appendChild(timeSpan);
        content.appendChild(metaLine);

        card.appendChild(content);

        // Close button
        var close = document.createElement('button');
        close.type = 'button';
        close.innerHTML = '&times;';
        close.style.cssText = 'position:absolute;top:8px;right:10px;background:rgba(255,255,255,0.2);color:white;border:none;width:24px;height:24px;border-radius:50%;cursor:pointer;font-size:16px;line-height:1;display:flex;align-items:center;justify-content:center;transition:background 0.2s;';
        close.onmouseenter = function() { close.style.background = 'rgba(255,255,255,0.3)'; };
        close.onmouseleave = function() { close.style.background = 'rgba(255,255,255,0.2)'; };
        close.onclick = function(e) {
            e.stopPropagation();
            if (loopTimer) {
                clearTimeout(loopTimer);
                loopTimer = null;
            }
            hidePopup(null);
        };
        card.appendChild(close);

        wrapper.appendChild(card);
        document.body.appendChild(wrapper);
        currentPopup = wrapper;

        // Animate in
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                wrapper.style.opacity = '1';
                wrapper.style.pointerEvents = 'auto';
                wrapper.style.transform = 'translateY(0)';
            });
        });

        // Schedule hide after display duration
        var displayDuration = settings.display_duration_ms || 6000;
        setTimeout(function() {
            hidePopup(onComplete);
        }, displayDuration);
    }

    function startLoop(items, settings) {
        if (!items || !items.length) {
            console.log('[Nomo Purchase Display] No recent purchases to show');
            return;
        }

        var index = 0;
        var delayBetween = settings.delay_between_ms || 4000;
        var displayDuration = settings.display_duration_ms || 6000;

        function showNext() {
            if (!items.length) return;
            
            showPurchase(items[index], settings, function() {
                // After popup hides, wait for delay then show next
                index = (index + 1) % items.length;
                
                if (!settings.loop && index === 0) {
                    return; // Stop if not looping and we've shown all
                }
                
                loopTimer = setTimeout(showNext, delayBetween);
            });
        }

        // Start the first one
        showNext();
    }

    function bootstrap() {
        if (!STORE_ID) {
            console.warn('[Nomo Purchase Display] Missing store ID');
            return;
        }

        fetchFeatureStatus().then(function(status) {
            if (!status.enabled) {
                console.log('[Nomo Purchase Display] Feature disabled for this store');
                return;
            }

            var settings = Object.assign({}, DEFAULT_SETTINGS, status.settings || {});

            fetchFeed(settings).then(function(feed) {
                if (!feed.enabled) {
                    console.log('[Nomo Purchase Display] Feed disabled or empty');
                    return;
                }
                var items = Array.isArray(feed.items) ? feed.items : [];
                if (feed.settings) {
                    settings = Object.assign(settings, feed.settings);
                }
                if (!items.length) {
                    console.log('[Nomo Purchase Display] No items returned from feed');
                    return;
                }
                startLoop(items, settings);
            });
        });
    }

    function resolveStoreIdAndStart() {
        if (STORE_ID && String(STORE_ID).trim()) {
            bootstrap();
            return;
        }

        var attempts = 0;
        var timer = setInterval(function() {
            attempts += 1;
            if (window.salla && typeof window.salla.config?.get === 'function') {
                STORE_ID = window.salla.config.get('store.id') || window.salla.config.get('merchant.id');
            } else if (window.Salla && window.Salla.store && window.Salla.store.id) {
                STORE_ID = window.Salla.store.id;
            }

            if (STORE_ID) {
                clearInterval(timer);
                bootstrap();
            } else if (attempts >= 10) {
                clearInterval(timer);
                console.warn('[Nomo Purchase Display] Could not determine store ID');
            }
        }, 300);
    }

    ready(resolveStoreIdAndStart);
})();
"""

    js_code = (
        script_template
        .replace('__DEFAULT_SETTINGS__', defaults_json)
        .replace('__BASE_URL__', base_url_json)
        .replace('__STORE_ID__', store_id_json)
    ).strip()

    response = HttpResponse(js_code, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response
