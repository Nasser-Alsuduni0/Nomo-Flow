from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from .models import PopupNotification
from .forms import PopupNotificationForm


def notifications_page(request):
    """Main notifications page with form and list"""
    notifications = PopupNotification.objects.all().order_by('-created_at')
    
    if request.method == 'POST':
        form = PopupNotificationForm(request.POST)
        if form.is_valid():
            # For now, we'll create without merchant (you can add authentication later)
            notification = form.save(commit=False)
            # notification.merchant = request.user.merchant  # Add when you have auth
            notification.save()
            messages.success(request, 'Notification created successfully!')
            return redirect('page-notifications')
    else:
        form = PopupNotificationForm()
    
    return render(request, 'dashboard/notifications.html', {
        'form': form,
        'notifications': notifications
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


def delete_notification(request, notification_id):
    """Delete a notification"""
    notification = get_object_or_404(PopupNotification, id=notification_id)
    notification.delete()
    
    return JsonResponse({'success': True})
