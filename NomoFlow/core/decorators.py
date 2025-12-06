"""
Authentication decorators
"""
from functools import wraps
from django.shortcuts import redirect
from django.http import HttpRequest
from .utils import get_current_merchant


def require_merchant_session(view_func):
    """
    Decorator to require a valid merchant session.
    Redirects to /app if no session exists.
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        merchant = get_current_merchant(request)
        if not merchant:
            # No session - redirect to app entry point
            return redirect('app_entry')
        return view_func(request, *args, **kwargs)
    return wrapper

