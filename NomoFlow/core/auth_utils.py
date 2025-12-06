"""
Authentication and token management utilities
"""
import requests
from typing import Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from .models import Merchant, SallaToken


def refresh_salla_token(merchant: Merchant) -> Tuple[bool, Optional[str]]:
    """
    Refresh Salla access token using refresh_token.
    
    Returns:
        (success: bool, error_message: Optional[str])
        On success, updates the token in database.
    """
    try:
        token = SallaToken.objects.filter(merchant=merchant).first()
        if not token or not token.refresh_token:
            return False, "No refresh token available"
        
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.SALLA_CLIENT_ID,
            "client_secret": settings.SALLA_CLIENT_SECRET,
            "refresh_token": token.refresh_token,
        }
        
        response = requests.post(settings.SALLA_OAUTH_TOKEN_URL, data=data, timeout=20)
        
        if response.status_code != 200:
            error_text = response.text
            print(f"🔴 Token Refresh FAILED for merchant {merchant.salla_merchant_id}: {response.status_code} - {error_text}")
            return False, f"Token refresh failed: {response.status_code}"
        
        token_json = response.json()
        new_access_token = token_json.get("access_token")
        new_refresh_token = token_json.get("refresh_token", token.refresh_token)  # Keep old if not provided
        expires_in = token_json.get("expires_in", 0)
        
        if not new_access_token:
            return False, "No access token in refresh response"
        
        expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in or 0))
        
        token.access_token = new_access_token
        token.refresh_token = new_refresh_token
        token.expires_at = expires_at
        token.save()
        
        print(f"✅ Token refreshed successfully for merchant {merchant.salla_merchant_id}")
        return True, None
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Request error during token refresh: {str(e)}"
        print(f"🔴 {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during token refresh: {str(e)}"
        print(f"🔴 {error_msg}")
        return False, error_msg


def get_valid_access_token(merchant: Merchant) -> Tuple[Optional[str], Optional[str]]:
    """
    Get a valid access token for merchant, refreshing if necessary.
    
    Returns:
        (access_token: Optional[str], error_message: Optional[str])
        If error_message is not None, the token refresh failed and merchant should reconnect.
    """
    token = SallaToken.objects.filter(merchant=merchant).first()
    
    if not token:
        return None, "No token found - merchant needs to reconnect"
    
    # Check if token is expired or about to expire (within 5 minutes)
    if token.expires_at and timezone.now() >= (token.expires_at - timezone.timedelta(minutes=5)):
        # Token expired or about to expire, try to refresh
        success, error_msg = refresh_salla_token(merchant)
        if not success:
            # Refresh failed - mark merchant as disconnected
            merchant.is_connected = False
            merchant.save(update_fields=["is_connected"])
            return None, error_msg or "Token refresh failed - merchant needs to reconnect"
        
        # Reload token after refresh
        token.refresh_from_db()
    
    return token.access_token, None


def call_salla_api_with_refresh(merchant: Merchant, method: str, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
    """
    Call Salla API with automatic token refresh on 401 errors.
    
    Returns:
        (response: Optional[requests.Response], error_message: Optional[str])
        If error_message is not None, the API call failed and merchant should reconnect.
    """
    access_token, error_msg = get_valid_access_token(merchant)
    if error_msg:
        return None, error_msg
    
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {access_token}"
    headers.setdefault("Accept", "application/json")
    headers.setdefault("Content-Type", "application/json")
    kwargs["headers"] = headers
    
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
        
        # If we get 401, try refreshing token once
        if response.status_code == 401:
            # Check if it's an invalid token error
            error_data = response.json() if response.content else {}
            error_code = error_data.get("error", {}).get("code", "") if isinstance(error_data, dict) else ""
            
            if "invalid_token" in str(error_code).lower() or "unauthorized" in str(response.text).lower():
                print(f"🔄 Got 401, attempting token refresh for merchant {merchant.salla_merchant_id}")
                success, refresh_error = refresh_salla_token(merchant)
                
                if success:
                    # Retry with new token
                    access_token, _ = get_valid_access_token(merchant)
                    headers["Authorization"] = f"Bearer {access_token}"
                    kwargs["headers"] = headers
                    response = requests.request(method, url, timeout=30, **kwargs)
                    
                    if response.status_code == 401:
                        # Still 401 after refresh - merchant needs to reconnect
                        merchant.is_connected = False
                        merchant.save(update_fields=["is_connected"])
                        return None, "Token refresh succeeded but API still returns 401 - merchant needs to reconnect"
                else:
                    # Refresh failed - mark as disconnected
                    merchant.is_connected = False
                    merchant.save(update_fields=["is_connected"])
                    return None, refresh_error or "Token refresh failed - merchant needs to reconnect"
        
        return response, None
        
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

