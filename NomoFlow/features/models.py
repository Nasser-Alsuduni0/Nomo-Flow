from django.db import models


class Feature(models.Model):
    key = models.CharField(
        max_length=50,
        unique=True,
        help_text="notifications | coupons | live_counter | email_collector | visitor_data | latest_conversion | recent_purchases",
    )
    title = models.CharField(max_length=120)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feature"
        verbose_name_plural = "Features"

    def __str__(self) -> str:
        return self.key


class MerchantFeature(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="merchant_features")
    feature = models.ForeignKey("features.Feature", on_delete=models.CASCADE, related_name="merchant_features")
    is_enabled = models.BooleanField(default=False)
    settings_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "feature"], name="uq_merchant_feature"),
        ]
        verbose_name = "Merchant Feature"
        verbose_name_plural = "Merchant Features"

    def __str__(self) -> str:
        return f"{self.merchant_id}:{self.feature_id} -> {'on' if self.is_enabled else 'off'}"
