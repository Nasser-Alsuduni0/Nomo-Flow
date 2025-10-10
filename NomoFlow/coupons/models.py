from django.db import models
from decimal import Decimal


class Coupon(models.Model):
    PERCENT = "percent"
    FIXED = "fixed"
    DISCOUNT_KIND_CHOICES = [
        (PERCENT, "Percentage of total purchases"),
        (FIXED, "Fixed amount"),
    ]

    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="coupons")
    
    # Coupon code (letters, numbers, no spaces)
    code = models.CharField(max_length=40, verbose_name="Coupon Code")
    
    # Discount type
    discount_kind = models.CharField(
        max_length=10, 
        choices=DISCOUNT_KIND_CHOICES,
        verbose_name="Discount Type"
    )
    
    # Discount percentage or amount
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name="Discount Amount"
    )
    
    # Maximum discount amount
    max_discount_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Maximum Discount Amount"
    )
    
    # Coupon start date
    start_date = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Start Date"
    )
    
    # Coupon expiry date
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Expiry Date"
    )
    
    # Free shipping
    free_shipping = models.BooleanField(
        default=False,
        verbose_name="Free Shipping"
    )
    
    # Exclude discounted products
    exclude_discounted = models.BooleanField(
        default=False,
        verbose_name="Exclude Discounted Products"
    )
    
    # Minimum cart value (excluding tax)
    min_cart = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        verbose_name="Minimum Cart Value"
    )
    
    # Maximum total uses
    max_uses = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Maximum Total Uses"
    )
    
    # Maximum uses per customer
    per_customer_limit = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Maximum Uses Per Customer"
    )
    
    salla_coupon_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "code"], name="uq_coupon_code_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["expires_at"]),
            models.Index(fields=["start_date"]),
        ]
        verbose_name = "Coupon"
        verbose_name_plural = "Coupons"

    def __str__(self) -> str:
        return f"{self.code} ({self.discount_kind} {self.amount})"
