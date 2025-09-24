from django.db import models


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
