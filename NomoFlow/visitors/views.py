from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from core.utils import get_current_merchant
from core.models import Merchant
from .models import VisitorSession, PageView
from features.models import MerchantFeature, Feature
import json
import hashlib
import uuid


def live_view_counter_page(request):
    """Dashboard page for live view counter"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    # Get or create the live_counter feature
    feature, _ = Feature.objects.get_or_create(
        key='live_counter',
        defaults={
            'title': 'Live View Counter',
            'description': 'Show real-time visitor count on your store'
        }
    )
    
    merchant_feature, _ = MerchantFeature.objects.get_or_create(
        merchant=merchant,
        feature=feature,
        defaults={'is_enabled': False}
    )
    
    # Get active sessions (last 5 minutes)
    active_threshold = timezone.now() - timedelta(minutes=5)
    active_sessions = VisitorSession.objects.filter(
        merchant=merchant,
        last_seen_at__gte=active_threshold
    ).count()
    
    # Get stats
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_sessions = VisitorSession.objects.filter(
        merchant=merchant,
        started_at__gte=today_start
    ).count()
    
    today_views = PageView.objects.filter(
        merchant=merchant,
        viewed_at__gte=today_start
    ).count()
    
    # Last 24 hours
    last_24h = now - timedelta(hours=24)
    sessions_24h = VisitorSession.objects.filter(
        merchant=merchant,
        started_at__gte=last_24h
    ).count()
    
    context = {
        'merchant': merchant,
        'is_enabled': merchant_feature.is_enabled,
        'active_visitors': active_sessions,
        'today_sessions': today_sessions,
        'today_views': today_views,
        'sessions_24h': sessions_24h,
    }
    
    return render(request, 'visitors/live_view_counter.html', context)


@require_http_methods(["POST"])
def toggle_feature(request):
    """Toggle live view counter feature on/off"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'success': False, 'message': 'No merchant selected'}, status=400)
    
    try:
        data = json.loads(request.body)
        enabled = data.get('enabled', False)
        
        feature, _ = Feature.objects.get_or_create(
            key='live_counter',
            defaults={
                'title': 'Live View Counter',
                'description': 'Show real-time visitor count on your store'
            }
        )
        
        merchant_feature, _ = MerchantFeature.objects.get_or_create(
            merchant=merchant,
            feature=feature
        )
        merchant_feature.is_enabled = enabled
        merchant_feature.save()
        
        return JsonResponse({
            'success': True,
            'is_enabled': enabled,
            'message': f'Live View Counter {"enabled" if enabled else "disabled"} successfully'
        })
    except Exception as e:
        print(f"Error in toggle_feature: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def is_feature_enabled(request):
    """Check if live view counter is enabled for a store"""
    store_id = request.GET.get('store_id')
    
    if not store_id:
        response = JsonResponse({'enabled': False, 'message': 'Store ID required'})
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
        feature = Feature.objects.filter(key='live_counter').first()
        
        if not feature:
            response = JsonResponse({'enabled': False})
            response['Access-Control-Allow-Origin'] = '*'
            return response
        
        merchant_feature = MerchantFeature.objects.filter(
            merchant=merchant,
            feature=feature
        ).first()
        
        if not merchant_feature:
            response = JsonResponse({'enabled': False})
            response['Access-Control-Allow-Origin'] = '*'
            return response
        
        response = JsonResponse({'enabled': merchant_feature.is_enabled})
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Merchant.DoesNotExist:
        response = JsonResponse({'enabled': False, 'message': 'Store not found'})
        response['Access-Control-Allow-Origin'] = '*'
        return response


@require_http_methods(["POST"])
@csrf_exempt
def track_visit(request):
    """Track a visitor session"""
    try:
        data = json.loads(request.body)
        store_id = data.get('store_id')
        session_id = data.get('session_id')
        page_path = data.get('page', '/')
        
        if not store_id or not session_id:
            return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)
        
        try:
            merchant = Merchant.objects.get(salla_merchant_id=store_id)
        except Merchant.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Store not found'}, status=404)
        
        now = timezone.now()
        
        # Update or create visitor session
        session, created = VisitorSession.objects.update_or_create(
            merchant=merchant,
            session_id=session_id,
            defaults={
                'started_at': now,
                'last_seen_at': now,
            }
        )
        
        # Always update last_seen_at for existing sessions
        if not created:
            session.last_seen_at = now
            session.save(update_fields=['last_seen_at'])
        
        # Track page view
        PageView.objects.create(
            merchant=merchant,
            session_id=session_id,
            path=page_path,
            viewed_at=now
        )
        
        # Get active visitor count
        active_threshold = now - timedelta(minutes=5)
        active_count = VisitorSession.objects.filter(
            merchant=merchant,
            last_seen_at__gte=active_threshold
        ).count()
        
        return JsonResponse({
            'success': True,
            'active_visitors': active_count
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in track_visit: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred'}, status=500)


@require_http_methods(["GET"])
def get_live_count(request):
    """Get current active visitor count"""
    store_id = request.GET.get('store_id')
    
    if not store_id:
        response = JsonResponse({'count': 0, 'message': 'Store ID required'})
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
        
        # Get active sessions (last 5 minutes)
        active_threshold = timezone.now() - timedelta(minutes=5)
        active_count = VisitorSession.objects.filter(
            merchant=merchant,
            last_seen_at__gte=active_threshold
        ).count()
        
        response = JsonResponse({'count': active_count})
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Merchant.DoesNotExist:
        response = JsonResponse({'count': 0, 'message': 'Store not found'})
        response['Access-Control-Allow-Origin'] = '*'
        return response


def live_counter_embed_js(request):
    """Generate the live counter embed JavaScript"""
    store_id = request.GET.get('store_id', '')
    
    # Force HTTPS for external requests
    base_url = f"https://{request.get_host()}"
    
    js_code = f"""
(function() {{
    'use strict';
    
    // Prevent double-loading
    if (window.__NOMO_LIVE_COUNTER_LOADED__) {{
        console.log('[Nomo Live Counter] Already loaded, skipping');
        return;
    }}
    window.__NOMO_LIVE_COUNTER_LOADED__ = true;
    
    const BASE_URL = '{base_url}';
    const STORE_ID = '{store_id}';
    
    // Generate or get session ID
    function getSessionId() {{
        let sessionId = sessionStorage.getItem('nomo_session_id');
        if (!sessionId) {{
            sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('nomo_session_id', sessionId);
        }}
        return sessionId;
    }}
    
    const SESSION_ID = getSessionId();
    
    // Check if feature is enabled
    fetch(BASE_URL + '/visitors/is-enabled/?store_id=' + encodeURIComponent(STORE_ID), {{
        headers: {{
            'ngrok-skip-browser-warning': 'true'
        }}
    }})
    .then(response => {{
        if (!response.ok) {{
            console.error('[Nomo Live Counter] API error:', response.status);
            return {{ enabled: false }};
        }}
        return response.json();
    }})
    .then(data => {{
        if (!data.enabled) {{
            console.log('[Nomo Live Counter] Feature is disabled for this store');
            return;
        }}
        
        // Initialize the live counter
        initLiveCounter();
    }})
    .catch(error => {{
        console.error('[Nomo Live Counter] Error checking feature status:', error);
    }});
    
    function initLiveCounter() {{
        // Track initial visit
        trackVisit();
        
        // Track every 30 seconds
        setInterval(trackVisit, 30000);
        
        // Create and show the counter badge
        showCounterBadge();
        
        // Update counter every 10 seconds
        setInterval(updateCounter, 10000);
    }}
    
    function trackVisit() {{
        const pagePath = window.location.pathname;
        
        fetch(BASE_URL + '/visitors/track/', {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            }},
            body: JSON.stringify({{
                store_id: STORE_ID,
                session_id: SESSION_ID,
                page: pagePath
            }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success && data.active_visitors) {{
                updateBadgeCount(data.active_visitors);
            }}
        }})
        .catch(error => {{
            console.error('[Nomo Live Counter] Track error:', error);
        }});
    }}
    
    function updateCounter() {{
        fetch(BASE_URL + '/visitors/live-count/?store_id=' + encodeURIComponent(STORE_ID), {{
            headers: {{
                'ngrok-skip-browser-warning': 'true'
            }}
        }})
        .then(response => response.json())
        .then(data => {{
            updateBadgeCount(data.count);
        }})
        .catch(error => {{
            console.error('[Nomo Live Counter] Update error:', error);
        }});
    }}
    
    function showCounterBadge() {{
        // Remove existing badge
        const existing = document.getElementById('nomo-live-counter-badge');
        if (existing) {{
            existing.remove();
        }}
        
        const badge = document.createElement('div');
        badge.id = 'nomo-live-counter-badge';
        badge.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 16px;
            border-radius: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            font-weight: 600;
            z-index: 999999;
            display: flex;
            align-items: center;
            gap: 8px;
            animation: nomoFadeIn 0.3s ease-out;
        `;
        
        badge.innerHTML = `
            <style>
                @keyframes nomoFadeIn {{
                    from {{ opacity: 0; transform: translateY(10px); }}
                    to {{ opacity: 1; transform: translateY(0); }}
                }}
                @keyframes nomoPulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                }}
                .nomo-pulse {{
                    width: 8px;
                    height: 8px;
                    background: #10b981;
                    border-radius: 50%;
                    animation: nomoPulse 2s infinite;
                }}
            </style>
            <span class="nomo-pulse"></span>
            <span id="nomo-counter-text">... visitors online</span>
        `;
        
        document.body.appendChild(badge);
    }}
    
    function updateBadgeCount(count) {{
        const textElement = document.getElementById('nomo-counter-text');
        if (textElement) {{
            const displayCount = Math.max(count, 1); // Always show at least 1
            textElement.textContent = displayCount + ' ' + (displayCount === 1 ? 'visitor' : 'visitors') + ' online';
        }}
    }}
}})();
""".strip()
    
    return HttpResponse(js_code, content_type='application/javascript')
