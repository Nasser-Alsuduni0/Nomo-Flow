"""
Marketing AI Engine
Provides intelligent marketing suggestions based on store data
"""
from django.db.models import Count, Sum, Avg, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


def get_marketing_suggestions(merchant):
    """Generate marketing suggestions for a merchant"""
    suggestions = {
        'notification_timing': get_notification_timing_suggestions(merchant),
        'coupon_strategy': get_coupon_strategy_suggestions(merchant),
        'target_audience': get_target_audience_suggestions(merchant),
    }
    return suggestions


def get_notification_timing_suggestions(merchant):
    """Analyze customer activity to suggest optimal notification times"""
    from recommendations.models import Order, CustomerInteraction
    from visitors.models import VisitorSession
    
    suggestions = []
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    
    # Analyze order timing
    orders = Order.objects.filter(
        merchant=merchant,
        ordered_at__gte=thirty_days_ago
    )
    
    if orders.exists():
        # Group orders by hour of day
        hourly_orders = {}
        for order in orders:
            if order.ordered_at:
                hour = order.ordered_at.hour
                hourly_orders[hour] = hourly_orders.get(hour, 0) + 1
        
        if hourly_orders:
            # Find peak hours
            sorted_hours = sorted(hourly_orders.items(), key=lambda x: x[1], reverse=True)
            peak_hour = sorted_hours[0][0]
            
            # Convert to readable format
            if peak_hour < 12:
                time_str = f"{peak_hour}:00 AM" if peak_hour != 0 else "12:00 AM"
            else:
                time_str = f"{peak_hour - 12}:00 PM" if peak_hour != 12 else "12:00 PM"
            
            suggestions.append({
                'icon': 'bi-clock',
                'title': 'Peak Shopping Hour',
                'description': f'Most orders are placed around {time_str}. Schedule notifications 1-2 hours before.',
                'priority': 'high',
                'action': f'Send notifications at {(peak_hour - 1) % 24}:00'
            })
        
        # Analyze day of week
        daily_orders = {}
        for order in orders:
            if order.ordered_at:
                day = order.ordered_at.strftime('%A')
                daily_orders[day] = daily_orders.get(day, 0) + 1
        
        if daily_orders:
            sorted_days = sorted(daily_orders.items(), key=lambda x: x[1], reverse=True)
            peak_day = sorted_days[0][0]
            suggestions.append({
                'icon': 'bi-calendar-week',
                'title': 'Best Day for Promotions',
                'description': f'{peak_day} has the highest order volume. Focus your marketing efforts on this day.',
                'priority': 'high',
                'action': f'Schedule campaigns for {peak_day}'
            })
    else:
        suggestions.append({
            'icon': 'bi-info-circle',
            'title': 'Not Enough Data',
            'description': 'We need more orders to analyze shopping patterns. Once you have sales, we\'ll provide timing insights.',
            'priority': 'low',
            'action': 'Keep promoting your store'
        })
    
    # Analyze visitor sessions
    sessions = VisitorSession.objects.filter(
        merchant=merchant,
        last_seen_at__gte=thirty_days_ago
    )
    
    if sessions.count() > 10:
        # Suggest based on visitor patterns
        suggestions.append({
            'icon': 'bi-bell',
            'title': 'Push Notification Strategy',
            'description': 'Send notifications in the evening (7-9 PM) when users are most likely to browse on mobile.',
            'priority': 'medium',
            'action': 'Schedule evening notifications'
        })
    
    return suggestions


def get_coupon_strategy_suggestions(merchant):
    """Suggest coupon strategies based on store performance"""
    from coupons.models import Coupon
    from recommendations.models import Order
    
    suggestions = []
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    
    # Get current coupons
    coupons = Coupon.objects.filter(merchant=merchant)
    active_coupons = coupons.filter(is_active=True)
    
    # Get order data
    orders = Order.objects.filter(
        merchant=merchant,
        ordered_at__gte=thirty_days_ago
    )
    
    total_orders = orders.count()
    total_revenue = orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    avg_order = total_revenue / total_orders if total_orders > 0 else Decimal('0')
    
    # Coupon suggestions
    if active_coupons.count() == 0:
        suggestions.append({
            'icon': 'bi-tag',
            'title': 'Create Your First Coupon',
            'description': 'You don\'t have any active coupons. Create a welcome discount to attract new customers.',
            'priority': 'high',
            'action': 'Create 10% welcome coupon',
            'action_url': '/dashboard/discount-coupons/'
        })
    elif active_coupons.count() < 3:
        suggestions.append({
            'icon': 'bi-tags',
            'title': 'Diversify Your Coupons',
            'description': 'Create different types of coupons: percentage off, free shipping, and buy-one-get-one.',
            'priority': 'medium',
            'action': 'Add more coupon types'
        })
    
    # Revenue-based suggestions
    if float(avg_order) > 0:
        threshold = float(avg_order) * 1.5
        suggestions.append({
            'icon': 'bi-cart-plus',
            'title': 'Increase Average Order Value',
            'description': f'Your average order is {float(avg_order):.0f} SAR. Offer free shipping over {threshold:.0f} SAR to increase cart size.',
            'priority': 'high',
            'action': f'Create "Free shipping over {threshold:.0f} SAR" coupon'
        })
    
    # Seasonal suggestions
    month = now.month
    if month in [11, 12]:  # Holiday season
        suggestions.append({
            'icon': 'bi-gift',
            'title': 'Holiday Season Promotion',
            'description': 'Create festive discounts and gift bundles to capitalize on holiday shopping.',
            'priority': 'high',
            'action': 'Launch holiday campaign'
        })
    elif month in [6, 7, 8]:  # Summer
        suggestions.append({
            'icon': 'bi-sun',
            'title': 'Summer Sale Opportunity',
            'description': 'Summer is a great time for clearance sales. Consider discounting seasonal items.',
            'priority': 'medium',
            'action': 'Create summer sale'
        })
    
    # First-time buyer focus
    suggestions.append({
        'icon': 'bi-person-plus',
        'title': 'Welcome New Customers',
        'description': 'First-time buyer discounts (10-15%) can increase conversion rates by up to 30%.',
        'priority': 'high',
        'action': 'Create first-purchase coupon'
    })
    
    return suggestions


def get_target_audience_suggestions(merchant):
    """Suggest target audience strategies based on customer data"""
    from recommendations.models import Customer, Order, CustomerInteraction
    
    suggestions = []
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    ninety_days_ago = now - timedelta(days=90)
    
    # Get customer data
    customers = Customer.objects.filter(merchant=merchant)
    total_customers = customers.count()
    
    # Recent vs old customers
    recent_customers = customers.filter(created_at__gte=thirty_days_ago).count()
    
    if total_customers > 0:
        new_customer_rate = (recent_customers / total_customers) * 100
        
        if new_customer_rate > 50:
            suggestions.append({
                'icon': 'bi-people',
                'title': 'Growing Customer Base',
                'description': f'{new_customer_rate:.0f}% of your customers are new. Focus on retention with loyalty programs.',
                'priority': 'high',
                'action': 'Create loyalty rewards'
            })
        else:
            suggestions.append({
                'icon': 'bi-person-heart',
                'title': 'Loyal Customer Focus',
                'description': 'Most customers are returning buyers. Reward them with exclusive VIP discounts.',
                'priority': 'medium',
                'action': 'Create VIP tier discounts'
            })
    
    # Order frequency analysis
    orders = Order.objects.filter(merchant=merchant)
    if orders.exists():
        # Customers with multiple orders
        repeat_buyers = orders.values('customer').annotate(
            order_count=Count('id')
        ).filter(order_count__gt=1).count()
        
        if total_customers > 0:
            repeat_rate = (repeat_buyers / total_customers) * 100 if total_customers > 0 else 0
            
            if repeat_rate < 20:
                suggestions.append({
                    'icon': 'bi-arrow-repeat',
                    'title': 'Boost Repeat Purchases',
                    'description': f'Only {repeat_rate:.0f}% are repeat buyers. Send follow-up emails with product recommendations.',
                    'priority': 'high',
                    'action': 'Set up post-purchase emails'
                })
            else:
                suggestions.append({
                    'icon': 'bi-trophy',
                    'title': 'Great Retention Rate!',
                    'description': f'{repeat_rate:.0f}% repeat purchase rate. Keep engaging these loyal customers.',
                    'priority': 'low',
                    'action': 'Maintain engagement strategy'
                })
    
    # Dormant customer reactivation
    if total_customers > 10:
        dormant_customers = customers.filter(
            created_at__lt=ninety_days_ago
        ).exclude(
            orders__ordered_at__gte=thirty_days_ago
        ).count()
        
        if dormant_customers > 5:
            suggestions.append({
                'icon': 'bi-envelope-heart',
                'title': 'Win Back Inactive Customers',
                'description': f'You have {dormant_customers} customers who haven\'t purchased in 90+ days. Send them a "We miss you" coupon.',
                'priority': 'high',
                'action': 'Create reactivation campaign'
            })
    
    # High-value customer segment
    if orders.exists():
        avg_order = orders.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0')
        high_value_threshold = float(avg_order) * 2
        
        suggestions.append({
            'icon': 'bi-gem',
            'title': 'VIP Customer Segment',
            'description': f'Identify customers spending over {high_value_threshold:.0f} SAR and offer them exclusive benefits.',
            'priority': 'medium',
            'action': 'Create VIP customer list'
        })
    
    # General audience expansion
    suggestions.append({
        'icon': 'bi-megaphone',
        'title': 'Expand Your Reach',
        'description': 'Use social media ads targeting lookalike audiences based on your best customers.',
        'priority': 'medium',
        'action': 'Plan social media campaign'
    })
    
    return suggestions
