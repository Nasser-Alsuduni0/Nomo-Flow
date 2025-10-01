from django.db import models


class PopupNotification(models.Model):
    """Popup notifications that appear on Salla stores"""
    POPUP = "popup"
    BANNER = "banner"
    MODAL = "modal"
    TYPE_CHOICES = [
        (POPUP, "Popup"),
        (BANNER, "Banner"),
        (MODAL, "Modal"),
    ]
    
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="popup_notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=POPUP)
    is_active = models.BooleanField(default=True)
    show_delay = models.IntegerField(default=3, help_text="Delay in seconds before showing")
    auto_close = models.BooleanField(default=True)
    auto_close_delay = models.IntegerField(default=10, help_text="Auto close delay in seconds")
    position = models.CharField(max_length=20, default="top-right", help_text="Position on screen")
    background_color = models.CharField(max_length=7, default="#17a8ff", help_text="Hex color code")
    text_color = models.CharField(max_length=7, default="#ffffff", help_text="Hex color code")
    button_text = models.CharField(max_length=50, blank=True, help_text="Optional button text")
    button_url = models.URLField(blank=True, help_text="Optional button URL")
    target_pages = models.TextField(blank=True, help_text="Comma-separated page patterns to show on")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Popup Notification"
        verbose_name_plural = "Popup Notifications"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.notification_type})"


class Notification(models.Model):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    CHANNEL_CHOICES = [
        (EMAIL, "email"),
        (SMS, "sms"),
        (WHATSAPP, "whatsapp"),
        (PUSH, "push"),
    ]

    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    template = models.TextField()
    is_scheduled = models.BooleanField(default=False)
    schedule_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_scheduled", "schedule_at"]),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        return f"{self.channel} scheduled={self.is_scheduled}"


class Message(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="messages")
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    channel = models.CharField(max_length=20, choices=Notification.CHANNEL_CHOICES)
    salla_customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    destination = models.CharField(max_length=254, null=True, blank=True)
    subject = models.TextField(null=True, blank=True)
    body_rendered = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("queued", "queued"),
            ("sent", "sent"),
            ("delivered", "delivered"),
            ("failed", "failed"),
        ],
        default="queued",
    )
    provider_message_id = models.CharField(max_length=150, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["notification"]),
            models.Index(fields=["salla_customer_id"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self) -> str:
        return f"{self.channel} -> {self.destination} [{self.status}]"
