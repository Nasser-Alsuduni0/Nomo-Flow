from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from marketing.models import Campaign
from coupons.models import Coupon
from visitors.models import VisitorSession, PageView
from core.utils import get_current_merchant
from recommendations.models import Order

def dashboard_metrics(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    merchant = get_current_merchant(request)

    # Visitor metrics
    if merchant:
        visitors = VisitorSession.objects.filter(merchant=merchant, last_seen_at__gte=week_ago)
        page_views = PageView.objects.filter(merchant=merchant, viewed_at__gte=week_ago)
        coupons = Coupon.objects.filter(merchant=merchant)
    else:
        visitors = VisitorSession.objects.filter(last_seen_at__gte=week_ago)
        page_views = PageView.objects.filter(viewed_at__gte=week_ago)
        coupons = Coupon.objects.all()

    total_visitors = visitors.count()
    total_page_views = page_views.count()
    total_coupons = coupons.count()
    
    # Estimate revenue (can be replaced with real revenue tracking later)
    # For now, estimate based on coupons and visitors
    estimated_revenue = total_coupons * 100 + total_visitors * 5  # Placeholder calculation

    data = {
        "total_visitors": total_visitors,
        "total_page_views": total_page_views,
        "total_coupons": total_coupons,
        "estimated_revenue": float(estimated_revenue),
    }
    return JsonResponse(data)


def dashboard_recommendations(request):
    merchant = get_current_merchant(request)
    recs = []
    
    # Visitor-based recommendations
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    
    if merchant:
        visitors = VisitorSession.objects.filter(merchant=merchant, last_seen_at__gte=week_ago).count()
        coupons = Coupon.objects.filter(merchant=merchant).count()
    else:
        visitors = VisitorSession.objects.filter(last_seen_at__gte=week_ago).count()
        coupons = Coupon.objects.count()
    
    if visitors == 0:
        recs.append("No visitors this week — consider promoting your store on social media.")
    elif visitors < 10:
        recs.append("Low visitor traffic — try creating discount coupons to attract more customers.")
    else:
        recs.append(f"Great! You have {visitors} visitors this week — keep up the momentum!")
    
    if coupons == 0:
        recs.append("Create your first discount coupon to encourage purchases.")
    elif coupons < 3:
        recs.append("Consider creating more discount coupons to increase conversions.")
    
    recs += [
        "Use limited-time offers to create urgency and boost conversions.",
        "Monitor your visitor analytics to understand peak traffic times.",
        "Engage with visitors through personalized notifications.",
    ]

    return JsonResponse({"recommendations": recs})


def dashboard_campaigns(request):
    data = list(Campaign.objects.values("name", "status", "budget_total")[:10])
    return JsonResponse(data, safe=False)


def dashboard_performance(request):
    """Get visitor analytics data for last 7 days"""
    now = timezone.now()
    merchant = get_current_merchant(request)
    
    labels = []
    visitors_data = []
    page_views_data = []
    
    # Get data for each of the last 7 days
    for i in range(7):
        day = now - timedelta(days=6-i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get visitors and page views for this day
        if merchant:
            day_visitors = VisitorSession.objects.filter(
                merchant=merchant,
                last_seen_at__gte=day_start,
                last_seen_at__lte=day_end
            ).count()
            day_page_views = PageView.objects.filter(
                merchant=merchant,
                viewed_at__gte=day_start,
                viewed_at__lte=day_end
            ).count()
        else:
            day_visitors = VisitorSession.objects.filter(
                last_seen_at__gte=day_start,
                last_seen_at__lte=day_end
            ).count()
            day_page_views = PageView.objects.filter(
                viewed_at__gte=day_start,
                viewed_at__lte=day_end
            ).count()
        
        day_label = day.strftime('%a')
        labels.append(day_label)
        visitors_data.append(day_visitors)
        page_views_data.append(day_page_views)
    
    return JsonResponse({
        'labels': labels,
        'visitors': visitors_data,
        'page_views': page_views_data
    })


def dashboard_coupon_usage(request):
    """Get coupon usage statistics"""
    merchant = get_current_merchant(request)
    
    if merchant:
        coupons = Coupon.objects.filter(merchant=merchant)
    else:
        coupons = Coupon.objects.all()
    
    active_count = coupons.filter(is_active=True).count()
    inactive_count = coupons.filter(is_active=False).count()
    
    return JsonResponse({
        'labels': ['Active', 'Inactive'],
        'data': [active_count, inactive_count]
    })


def dashboard_traffic_sources(request):
    """Get traffic sources analytics"""
    merchant = get_current_merchant(request)
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    
    if merchant:
        sessions = VisitorSession.objects.filter(merchant=merchant, last_seen_at__gte=week_ago)
    else:
        sessions = VisitorSession.objects.filter(last_seen_at__gte=week_ago)
    
    # Group by source (if available) or use default
    direct_count = sessions.filter(source__isnull=True).count() + sessions.filter(source='').count()
    referral_count = sessions.exclude(source__isnull=True).exclude(source='').count()
    
    return JsonResponse({
        'labels': ['Direct', 'Referral'],
        'data': [direct_count, referral_count]
    })


def dashboard_sales(request):
    """Get sales analytics data by period (days, months, years)"""
    merchant = get_current_merchant(request)
    period = request.GET.get('period', 'days')
    now = timezone.now()
    
    labels = []
    sales_data = []
    
    if merchant:
        orders = Order.objects.filter(merchant=merchant)
    else:
        orders = Order.objects.all()
    
    if period == 'days':
        # Last 7 days
        for i in range(7):
            day = now - timedelta(days=6-i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            day_sales = orders.filter(
                ordered_at__gte=day_start,
                ordered_at__lte=day_end
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            day_label = day.strftime('%a, %b %d')
            labels.append(day_label)
            sales_data.append(float(day_sales))
    
    elif period == 'months':
        # Last 12 months
        for i in range(12):
            month_date = now - timedelta(days=30 * (11 - i))
            month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get next month start for the end date
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(seconds=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1) - timedelta(seconds=1)
            
            month_sales = orders.filter(
                ordered_at__gte=month_start,
                ordered_at__lte=month_end
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            month_label = month_start.strftime('%b %Y')
            labels.append(month_label)
            sales_data.append(float(month_sales))
    
    elif period == 'years':
        # Last 5 years
        current_year = now.year
        for i in range(5):
            year = current_year - (4 - i)
            year_start = now.replace(year=year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            year_end = now.replace(year=year, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            
            year_sales = orders.filter(
                ordered_at__gte=year_start,
                ordered_at__lte=year_end
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
            
            labels.append(str(year))
            sales_data.append(float(year_sales))
    
    # Calculate summary stats
    total_sales = sum(sales_data)
    total_orders_count = orders.count()
    avg_order = total_sales / total_orders_count if total_orders_count > 0 else 0
    
    return JsonResponse({
        'labels': labels,
        'sales': sales_data,
        'total_sales': total_sales,
        'total_orders': total_orders_count,
        'avg_order': avg_order
    })


def dashboard_marketing_suggestions(request):
    """Get AI marketing suggestions for the merchant"""
    merchant = get_current_merchant(request)
    
    if not merchant:
        return JsonResponse({
            'error': 'No merchant selected',
            'notification_timing': [],
            'coupon_strategy': [],
            'target_audience': []
        }, status=400)
    
    try:
        from dashboard.marketing_ai import get_marketing_suggestions
        suggestions = get_marketing_suggestions(merchant)
        return JsonResponse(suggestions)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'notification_timing': [],
            'coupon_strategy': [],
            'target_audience': []
        }, status=500)
