from django.db import models
from decimal import Decimal


class Merchant(models.Model):
    name = models.CharField(max_length=150)
    salla_merchant_id = models.CharField(max_length=100, unique=True, help_text="Store ID in Salla")
    owner_email = models.EmailField(max_length=254, null=True, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Riyadh")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Merchant"
        verbose_name_plural = "Merchants"

    def __str__(self) -> str:
        return f"{self.name} ({self.salla_merchant_id})"


class SallaToken(models.Model):
    merchant = models.OneToOneField(
        "core.Merchant",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="salla_token",
        help_text="1:1 with merchant",
    )
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    scope = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Salla Token"
        verbose_name_plural = "Salla Tokens"

    def __str__(self) -> str:
        return f"Token for {self.merchant_id} expires {self.expires_at}"


class Event(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80)
    salla_event_id = models.CharField(max_length=120, null=True, blank=True)
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["merchant"]),
            models.Index(fields=["event_type", "occurred_at"]),
        ]
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.occurred_at}"


class Attribution(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="attributions")
    coupon = models.ForeignKey("coupons.Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="attributions")
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attributions",
    )
    salla_order_id = models.CharField(max_length=100)
    salla_customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    revenue_sar = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    used_coupon_code = models.CharField(max_length=40, null=True, blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "salla_order_id"], name="uq_order_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["occurred_at"]),
        ]
        verbose_name = "Attribution"
        verbose_name_plural = "Attributions"

    def __str__(self) -> str:
        return f"Order {self.salla_order_id} revenue {self.revenue_sar}"


class EmailSubscriber(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="email_subscribers")
    email = models.EmailField(max_length=254)
    name = models.CharField(max_length=120, null=True, blank=True)
    source = models.CharField(max_length=60, null=True, blank=True)
    consent = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField()
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "email"], name="uq_email_per_merchant"),
        ]
        verbose_name = "Email Subscriber"
        verbose_name_plural = "Email Subscribers"

    def __str__(self) -> str:
        return f"{self.email} ({'consented' if self.consent else 'no consent'})"
