from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count
from django.core.paginator import Paginator
from core.utils import get_current_merchant
from core.models import Merchant, EmailSubscriber
from .models import MerchantFeature, Feature
from .forms import EmailSubscriberForm
import json


def email_collector_page(request):
    """Dashboard page for email collector"""
    merchant = get_current_merchant(request)
    if not merchant:
        return redirect('dashboard')
    
    # Get or create the email_collector feature and merchant feature
    feature, _ = Feature.objects.get_or_create(
        key='email_collector',
        defaults={
            'title': 'Email Collector',
            'description': 'Collect email subscribers from your store'
        }
    )
    
    merchant_feature, _ = MerchantFeature.objects.get_or_create(
        merchant=merchant,
        feature=feature,
        defaults={'is_enabled': False}
    )
    
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


@require_http_methods(["POST"])
def toggle_feature(request):
    """Toggle email collector feature on/off"""
    merchant = get_current_merchant(request)
    if not merchant:
        return JsonResponse({'success': False, 'message': 'No merchant selected'}, status=400)
    
    try:
        data = json.loads(request.body)
        enabled = data.get('enabled', False)
        
        # Get or create feature
        feature, _ = Feature.objects.get_or_create(
            key='email_collector',
            defaults={
                'title': 'Email Collector',
                'description': 'Collect email subscribers from your store'
            }
        )
        
        # Update or create merchant feature
        merchant_feature, _ = MerchantFeature.objects.get_or_create(
            merchant=merchant,
            feature=feature
        )
        merchant_feature.is_enabled = enabled
        merchant_feature.save()
        
        return JsonResponse({
            'success': True,
            'is_enabled': enabled,
            'message': f'Email Collector {"enabled" if enabled else "disabled"} successfully'
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
    """Check if email collector is enabled for a store"""
    store_id = request.GET.get('store_id')
    
    if not store_id:
        response = JsonResponse({'enabled': False, 'message': 'Store ID required'})
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    try:
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
        feature = Feature.objects.filter(key='email_collector').first()
        
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
