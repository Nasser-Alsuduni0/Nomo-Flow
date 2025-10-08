from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from .models import PopupNotification
from .forms import PopupNotificationForm
from django.views.decorators.http import require_GET
from django.http import HttpResponse


def notifications_page(request):
    """Main notifications page with form and list"""
    # Get the merchant with active OAuth token (actually connected store)
    from core.models import Merchant, SallaToken
    
    try:
        # Get the merchant that has an active OAuth token
        salla_token = SallaToken.objects.select_related('merchant').first()
        if salla_token:
            merchant = salla_token.merchant
        else:
            # Fallback: get the most recently created merchant
            merchant = Merchant.objects.order_by('-created_at').first()
    except:
        merchant = None
    
    if not merchant:
        # Create a demo merchant if none exists
        merchant, created = Merchant.objects.get_or_create(
            salla_merchant_id='demo-store-123',
            defaults={'name': 'Demo Store', 'owner_email': 'demo@example.com'}
        )
    
    notifications = PopupNotification.objects.filter(merchant=merchant).order_by('-created_at')
    
    if request.method == 'POST':
        form = PopupNotificationForm(request.POST)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.merchant = merchant
            notification.notification_type = 'popup'  # Always set to popup
            notification.save()
            messages.success(request, 'Notification created successfully!')
            return redirect('page-notifications')
    else:
        form = PopupNotificationForm()
    
    return render(request, 'dashboard/notifications.html', {
        'form': form,
        'notifications': notifications,
        'merchant': merchant
    })


def toggle_notification(request, notification_id):
    """Toggle notification active status"""
    notification = get_object_or_404(PopupNotification, id=notification_id)
    notification.is_active = not notification.is_active
    notification.save()
    
    return JsonResponse({
        'success': True,
        'is_active': notification.is_active
    })


def edit_notification(request, notification_id):
    """Edit a notification"""
    notification = get_object_or_404(PopupNotification, id=notification_id)
    
    if request.method == 'POST':
        form = PopupNotificationForm(request.POST, instance=notification)
        if form.is_valid():
            updated_notification = form.save(commit=False)
            updated_notification.notification_type = 'popup'  # Always set to popup
            updated_notification.save()
            return JsonResponse({'success': True, 'message': 'Notification updated successfully!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    
    # Return notification data for editing
    return JsonResponse({
        'success': True,
        'notification': {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'background_color': notification.background_color,
            'text_color': notification.text_color,
            'button_text': notification.button_text,
            'button_url': notification.button_url,
            'is_active': notification.is_active,
        }
    })


def delete_notification(request, notification_id):
    """Delete a notification"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'})
    
    try:
        notification = get_object_or_404(PopupNotification, id=notification_id)
        notification_title = notification.title
        notification.delete()
        return JsonResponse({'success': True, 'message': f'Notification "{notification_title}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def public_feed(request):
    """Public API endpoint for fetching notifications"""
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
        response['Access-Control-Max-Age'] = '86400'  # Cache for 24 hours
        return response
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    """Return active popup notifications as JSON for a specific merchant.
    
    Query params:
    - store_id: Salla merchant ID to filter notifications
    """
    store_id = request.GET.get('store_id')
    
    if not store_id:
        return JsonResponse({'notifications': []})
    
    try:
        # Get merchant by Salla ID
        from core.models import Merchant
        merchant = Merchant.objects.get(salla_merchant_id=store_id)
        
        items = list(PopupNotification.objects.filter(
            merchant=merchant, 
            is_active=True
        ).values(
            'id', 'title', 'message', 'notification_type', 'position', 
            'background_color', 'text_color', 'button_text', 'button_url', 'target_pages'
        ))
        response = JsonResponse({'notifications': items})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
        response['Access-Control-Max-Age'] = '86400'  # Cache for 24 hours
        return response
    except Merchant.DoesNotExist:
        response = JsonResponse({'notifications': []})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
        response['Access-Control-Max-Age'] = '86400'  # Cache for 24 hours
        return response


def embed_js(request):
    """Generate JavaScript embed code for notifications"""
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
    """
    Embeddable script to render notifications on merchant storefront.
    Usage:
      <script>
        window.__NOMO_BASE__ = 'https://<your-ngrok>.ngrok-free.app';
        window.__NOMO_STORE_ID__ = 'demo-store-123';
      </script>
      <script src="https://<your-ngrok>.ngrok-free.app/notifications/embed.js?store_id=demo-store-123" defer></script>
    """
    js = r"""
   (function(){
  // === Resolve script src & base origin ===
  var SCRIPT_EL = (function(){
    if (document.currentScript) return document.currentScript;
    var s = document.getElementsByTagName('script');
    return s.length ? s[s.length - 1] : null;
  })();
  var SCRIPT_SRC = (SCRIPT_EL && SCRIPT_EL.src) || '';

  // window.__NOMO_BASE__ إن ما تم ضبطه، خذ origin من رابط السكربت نفسه
  var BASE = (window.__NOMO_BASE__ || '').replace(/\/+$/,'');
  if (!BASE) {
    try {
      var u = new URL(SCRIPT_SRC);
      BASE = u.origin; // مثال: https://00f9b44061d9.ngrok-free.app
    } catch(e) {
      BASE = ''; // أخيرًا، بس غالبًا ما رح نوصلها
    }
  }

  function qsFromScript(name, src){
    var m = (src || '').match(new RegExp('[?&]'+name+'=([^&#]+)'));
    return m ? decodeURIComponent(m[1]) : null;
  }

  function isPlaceholder(v){
    return !v || /^\s*\{\{/.test(String(v)) || String(v).toLowerCase() === 'null' || String(v).toLowerCase() === 'undefined';
  }

  // store_id من query أو من global أو data-attribute
  var STORE_ID = qsFromScript('store_id', SCRIPT_SRC) || window.__NOMO_STORE_ID__ || (SCRIPT_EL && SCRIPT_EL.getAttribute('data-store-id')) || null;

  function ready(fn){
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function applyPosition(el, pos){
    var p = pos || 'bottom-left';
    // نضبط الخاصيات المطلوبة فقط
    if (p === 'top-left'){ el.style.top='20px'; el.style.left='20px'; }
    else if (p === 'top-right'){ el.style.top='20px'; el.style.right='20px'; }
    else if (p === 'bottom-left'){ el.style.bottom='20px'; el.style.left='20px'; }
    else if (p === 'bottom-right'){ el.style.bottom='20px'; el.style.right='20px'; }
    else if (p === 'top-center'){ el.style.top='20px'; el.style.left='50%'; el.style.transform='translateX(-50%)'; }
    else if (p === 'bottom-center'){ el.style.bottom='20px'; el.style.left='50%'; el.style.transform='translateX(-50%)'; }
    else { el.style.bottom='20px'; el.style.left='20px'; }
  }

  function createNotif(n){
    console.log('Nomo Flow: Creating notification element for:', n.title);
    
    var wrap = document.createElement('div');
    wrap.style.position = 'fixed';
    wrap.style.zIndex = '999999';
    wrap.style.opacity = '0';
    wrap.style.transform = 'translateY(20px)';
    wrap.style.transition = 'all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
    applyPosition(wrap, 'bottom-left');

    var card = document.createElement('div');
    card.style.maxWidth = '380px';
    card.style.minWidth = '300px';
    card.style.background = n.background_color || '#ffffff';
    card.style.color = n.text_color || '#333333';
    card.style.borderRadius = '16px';
    card.style.boxShadow = '0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.05)';
    card.style.padding = '20px 24px';
    card.style.fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif';
    card.style.position = 'relative';
    card.style.backdropFilter = 'blur(10px)';
    card.style.overflow = 'hidden';

    // Add decorative accent bar
    var accent = document.createElement('div');
    accent.style.position = 'absolute';
    accent.style.top = '0';
    accent.style.left = '0';
    accent.style.right = '0';
    accent.style.height = '4px';
    accent.style.background = 'linear-gradient(90deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0.8) 50%, rgba(255,255,255,0.4) 100%)';
    card.appendChild(accent);

    // Close button container
    var closeBtn = document.createElement('button');
    closeBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
    closeBtn.style.position = 'absolute';
    closeBtn.style.top = '16px';
    closeBtn.style.right = '16px';
    closeBtn.style.background = 'rgba(0,0,0,0.1)';
    closeBtn.style.border = 'none';
    closeBtn.style.borderRadius = '50%';
    closeBtn.style.width = '32px';
    closeBtn.style.height = '32px';
    closeBtn.style.display = 'flex';
    closeBtn.style.alignItems = 'center';
    closeBtn.style.justifyContent = 'center';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.color = n.text_color || '#333333';
    closeBtn.style.transition = 'all 0.2s ease';
    closeBtn.style.opacity = '0.6';
    closeBtn.style.padding = '0';
    closeBtn.setAttribute('aria-label', 'Close notification');
    
    closeBtn.onmouseover = function(){
      this.style.opacity = '1';
      this.style.background = 'rgba(0,0,0,0.2)';
      this.style.transform = 'scale(1.1)';
    };
    closeBtn.onmouseout = function(){
      this.style.opacity = '0.6';
      this.style.background = 'rgba(0,0,0,0.1)';
      this.style.transform = 'scale(1)';
    };
    closeBtn.onclick = function(){
      wrap.style.opacity = '0';
      wrap.style.transform = 'translateY(20px) scale(0.95)';
      setTimeout(function(){ 
        try{ wrap.remove(); }catch(e){} 
      }, 300);
    };
    card.appendChild(closeBtn);

    // Content container with flex layout for icon and text
    var content = document.createElement('div');
    content.style.display = 'flex';
    content.style.flexDirection = 'row';
    content.style.alignItems = 'flex-start';
    content.style.gap = '16px';
    content.style.paddingRight = '32px';
    content.style.direction = 'ltr'; // Force LTR for flex layout to keep icon on left
    
    // Notification icon on the left
    var iconContainer = document.createElement('div');
    iconContainer.style.flexShrink = '0';
    iconContainer.style.width = '48px';
    iconContainer.style.height = '48px';
    iconContainer.style.display = 'flex';
    iconContainer.style.alignItems = 'center';
    iconContainer.style.justifyContent = 'center';
    iconContainer.style.background = 'rgba(0,0,0,0.05)';
    iconContainer.style.borderRadius = '12px';
    iconContainer.innerHTML = '<svg width="28" height="28" viewBox="0 0 1800 1800" fill="currentColor" style="opacity:0.8"><path d="M1555.292,1240.33c-11.603-18.885-24.035-39.138-36.538-60.862c-1.408-5.24-4.108-9.945-7.79-13.722c-49.513-88.479-97.741-200.637-97.741-344.862c0-339.747-187.438-622.592-438.45-681.168c7.458-12.796,11.813-27.633,11.813-43.511c0-47.816-38.768-86.576-86.583-86.576c-47.813,0-86.581,38.759-86.581,86.576c0,15.878,4.35,30.715,11.813,43.511c-251.011,58.576-438.455,341.421-438.455,681.168c0,188.204-82.117,321.858-142.074,419.446c-47.275,76.945-81.431,132.54-53.413,182.688c34.706,62.133,150.24,84.154,527.356,89.08c-11.577,25.247-18.085,53.287-18.085,82.834c0,109.974,89.466,199.439,199.438,199.439c109.971,0,199.432-89.466,199.432-199.439c0-29.547-6.505-57.587-18.09-82.834c377.126-4.926,492.65-26.947,527.361-89.08C1636.728,1372.87,1602.566,1317.275,1555.292,1240.33z M900.002,1731.698c-75.415,0-136.767-61.352-136.767-136.767c0-30.793,10.234-59.236,27.477-82.121c34.47,0.25,70.82,0.385,109.26,0.424c0.021,0,0.039,0,0.061,0c38.438-0.039,74.783-0.174,109.26-0.424c17.231,22.885,27.471,51.328,27.471,82.121C1036.763,1670.347,975.412,1731.698,900.002,1731.698z"/></svg>';
    content.appendChild(iconContainer);
    
    // Text container on the right
    var textContainer = document.createElement('div');
    textContainer.style.flex = '1';
    textContainer.style.minWidth = '0';
    textContainer.style.textAlign = 'right'; // Align text to the right
    textContainer.style.direction = 'rtl'; // RTL text direction
    
    // Truncate title to 50 characters
    var titleText = (n.title || 'Notification');
    if (titleText.length > 50) titleText = titleText.substring(0, 50) + '...';

    var title = document.createElement('div');
    title.style.fontWeight = '700';
    title.style.fontSize = '18px';
    title.style.marginBottom = '8px';
    title.style.lineHeight = '1.4';
    title.style.letterSpacing = '-0.02em';
    title.style.wordWrap = 'break-word';
    title.style.overflowWrap = 'break-word';
    title.appendChild(document.createTextNode(titleText));
    textContainer.appendChild(title);
    
    // Truncate message to 120 characters
    var messageText = (n.message || '');
    if (messageText.length > 120) messageText = messageText.substring(0, 120) + '...';

    var msg = document.createElement('div');
    msg.style.fontWeight = '400';
    msg.style.fontSize = '15px';
    msg.style.lineHeight = '1.6';
    msg.style.opacity = '0.9';
    msg.style.wordWrap = 'break-word';
    msg.style.overflowWrap = 'break-word';
    msg.appendChild(document.createTextNode(messageText));
    textContainer.appendChild(msg);

    content.appendChild(textContainer);

    if (n.button_text && n.button_url){
      var a = document.createElement('a');
      a.textContent = n.button_text;
      a.href = n.button_url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.style.display = 'inline-flex';
      a.style.alignItems = 'center';
      a.style.gap = '6px';
      a.style.marginTop = '16px';
      a.style.padding = '10px 20px';
      a.style.fontWeight = '600';
      a.style.fontSize = '14px';
      a.style.background = 'rgba(255,255,255,0.95)';
      a.style.color = n.background_color || '#333333';
      a.style.borderRadius = '10px';
      a.style.textDecoration = 'none';
      a.style.transition = 'all 0.2s ease';
      a.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
      a.onmouseover = function(){
        this.style.transform = 'translateY(-2px)';
        this.style.boxShadow = '0 6px 20px rgba(0,0,0,0.2)';
      };
      a.onmouseout = function(){
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
      };
      
      // Add arrow icon to button
      a.innerHTML = a.textContent + ' <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>';
      textContainer.appendChild(a);
    }

    card.appendChild(content);
    wrap.appendChild(card);
    document.body.appendChild(wrap);
    console.log('Nomo Flow: Notification element added to DOM');

    // Show notification immediately (no delay)
    setTimeout(function(){ 
      wrap.style.opacity = '1';
      wrap.style.transform = 'translateY(0)';
      console.log('Nomo Flow: Notification should now be visible');
    }, 100);

    // Auto close removed - notification stays until user clicks close button

    return wrap;
  }

  function fetchAndRender(){
    console.log('Nomo Flow: Starting fetchAndRender, STORE_ID:', STORE_ID, 'BASE:', BASE);
    
    if (!STORE_ID) {
      console.warn('Nomo Flow: No STORE_ID found');
      return;
    }

    var url = BASE + '/notifications/feed/?store_id=' + encodeURIComponent(STORE_ID);
    console.log('Nomo Flow: Fetching notifications from:', url);

    fetch(url, { 
      method: 'GET',
      mode: 'cors',
      headers: {
        'Accept': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      }
    })
      .then(function(r){
        console.log('Nomo Flow: Response status:', r.status);
        console.log('Nomo Flow: Response URL:', r.url);
        console.log('Nomo Flow: Content-Type:', r.headers.get('Content-Type'));
        console.log('Nomo Flow: Response headers:', [...r.headers.entries()]);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        var ct = r.headers.get('Content-Type') || '';
        if (ct.indexOf('application/json') === -1) {
          console.error('Nomo Flow: Expected JSON but got Content-Type:', ct);
          // Try to get the response text to see what we actually got
          return r.text().then(function(text) {
            console.error('Nomo Flow: Response body:', text.substring(0, 500));
            throw new Error('Not JSON - Content-Type: ' + ct);
          });
        }
        return r.json();
      })
      .then(function(d){
        console.log('Nomo Flow: Received data:', d);
        var list = (d && d.notifications) || [];
        console.log('Nomo Flow: Notifications list:', list);
        
        if (!Array.isArray(list) || !list.length) {
          console.log('Nomo Flow: No notifications to show');
          return;
        }

        console.log('Nomo Flow: Showing', list.length, 'notifications');
        var idx = 0;
        (function showNext(){
          if (idx >= list.length) return;
          var n = list[idx++];
          console.log('Nomo Flow: Creating notification:', n.title);
          createNotif(n);
          // Show next notification after 5 seconds (if multiple notifications exist)
          if (idx < list.length) {
            setTimeout(showNext, 5000);
          }
        })();
      })
      .catch(function(err){
        console.error('Nomo Flow: Error fetching notifications:', err);
      });
  }

  // === Resolve STORE_ID if missing/placeholder ===
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

  function resolveStoreIdAndStart(){
    if (isPlaceholder(STORE_ID)) {
      var fromSalla = tryGetFromSalla();
      if (fromSalla) {
        STORE_ID = fromSalla;
      }
    }

    if (isPlaceholder(STORE_ID)) {
      var attempts = 0;
      var timer = setInterval(function(){
        attempts += 1;
        var sId = tryGetFromSalla();
        if (sId) {
          clearInterval(timer);
          STORE_ID = sId;
          fetchAndRender();
        } else if (attempts >= 10) {
          clearInterval(timer);
          console.warn('Nomo Flow: Could not resolve STORE_ID');
        }
      }, 300);
    } else {
      fetchAndRender();
    }
  }

  ready(resolveStoreIdAndStart);
})();

    """
    response = HttpResponse(js, content_type='application/javascript')
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response


def generate_snippet(request):
    """
    Generate a dynamic snippet for the current merchant.
    This endpoint can be called from the dashboard to get the correct snippet.
    """
    from core.models import Merchant
    
    # Get the current merchant from the request (you might need to implement merchant detection)
    # For now, we'll use a query parameter or session
    merchant_id = request.GET.get('merchant_id')
    
    if not merchant_id:
        return JsonResponse({'error': 'Merchant ID required'}, status=400)
    
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        return JsonResponse({'error': 'Merchant not found'}, status=404)
    
    # Get the current base URL
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    # Generate the snippet
    snippet = f"""<script>
  window._NOMO_BASE_ = '{base_url}';
  window._NOMO_STORE_ID_ = '{merchant.salla_merchant_id}';
</script>
<script src="{base_url}/notifications/embed.js?store_id={merchant.salla_merchant_id}&v=7" defer></script>"""
    
    return JsonResponse({
        'snippet': snippet,
        'merchant_id': merchant.id,
        'merchant_name': merchant.name,
        'salla_store_id': merchant.salla_merchant_id,
        'base_url': base_url
    })
