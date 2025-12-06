from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .utils import get_current_merchant, set_current_merchant, clear_current_merchant, SESSION_KEY_CURRENT_MERCHANT_ID
from .models import Merchant, SallaToken


def home(request):
    return render(request, 'core/home.html')


@require_http_methods(["GET"])
def app_entry(request):
    """
    Entry point for the app (/app).
    Checks for valid session and redirects accordingly.
    If app was installed from Salla Store, auto-create session if merchant exists.
    """
    merchant = get_current_merchant(request)
    
    if merchant:
        # Valid session exists - redirect to dashboard
        return redirect('dashboard')
    
    # Check if user just logged out - don't auto-create session in this case
    # This prevents auto-login after logout
    if request.GET.get('logged_out') == 'true' or 'logout' in request.META.get('HTTP_REFERER', ''):
        # User just logged out - show login page without auto-creating session
        return render(request, 'core/app_entry.html', {
            'show_connect_button': True
        })
    
    # No session - check if merchant exists with valid token (app installed from Salla Store)
    # Try to find merchant by checking for valid tokens
    from core.models import SallaToken
    from django.utils import timezone
    
    # Find token that is not expired (or expires within next 5 minutes)
    now = timezone.now()
    token = SallaToken.objects.select_related('merchant').filter(
        merchant__is_connected=True,
        expires_at__gt=now - timezone.timedelta(minutes=5)  # Token not expired (with 5 min buffer)
    ).first()
    
    if token and token.merchant:
        # Merchant exists with valid token - auto-create session
        # This happens when app is installed from Salla Store
        try:
            set_current_merchant(request, token.merchant)
            print(f"✅ Auto-created session for merchant {token.merchant.salla_merchant_id} (installed from Salla Store)")
            return redirect('dashboard')
        except Exception as e:
            print(f"⚠️ Failed to auto-create session: {e}")
            # Fall through to show login page
    
    # No session and no valid merchant - show "Continue with Salla" button
    return render(request, 'core/app_entry.html', {
        'show_connect_button': True
    })


@require_http_methods(["POST", "GET"])
def logout(request):
    """
    Logout: Clear session cookie/JWT only.
    Keeps merchant data and tokens in database.
    """
    try:
        clear_current_merchant(request)
        messages.success(request, 'تم تسجيل الخروج بنجاح')
        print(f"✅ User logged out successfully")
    except Exception as e:
        print(f"⚠️ Error during logout: {e}")
        messages.error(request, 'حدث خطأ أثناء تسجيل الخروج')
    # Redirect to home page instead of login page
    return redirect('home')


@require_http_methods(["POST", "GET"])
def disconnect(request):
    """
    Disconnect: Delete tokens and mark merchant as disconnected.
    Merchant account remains but in disconnected state.
    """
    merchant = get_current_merchant(request)
    
    if not merchant:
        messages.error(request, 'لا توجد جلسة نشطة')
        return redirect('app_entry')
    
    # If GET request, show confirmation page
    if request.method == "GET":
        return render(request, 'core/disconnect_confirm.html', {
            'merchant': merchant
        })
    
    # POST request - proceed with disconnection
    merchant_name = merchant.name
    
    # Delete tokens
    SallaToken.objects.filter(merchant=merchant).delete()
    
    # Mark as disconnected
    merchant.is_connected = False
    merchant.save(update_fields=["is_connected"])
    
    # Clear session
    clear_current_merchant(request)
    
    messages.success(request, f'تم قطع الاتصال مع متجر "{merchant_name}" بنجاح')
    return redirect('app_entry')
