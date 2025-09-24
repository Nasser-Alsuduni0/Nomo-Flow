from django.db import models
from decimal import Decimal


class Coupon(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    DISCOUNT_KIND_CHOICES = [
        (PERCENT, "percent"),
        (FIXED, "fixed"),
    ]

    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="coupons")
    code = models.CharField(max_length=40)
    discount_kind = models.CharField(max_length=10, choices=DISCOUNT_KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    min_cart = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_uses = models.IntegerField(null=True, blank=True)
    per_customer_limit = models.IntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    salla_coupon_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "code"], name="uq_coupon_code_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

    def __str__(self) -> str:
        return f"{self.code} ({self.discount_kind} {self.amount})"
