from django.db import models


class Integration(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="integrations")
    webhook_secret = models.TextField(null=True, blank=True)
    api_base_url = models.TextField(null=True, blank=True)
    settings_json = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integration"
        verbose_name_plural = "Integrations"

    def __str__(self) -> str:
        return f"Integration for {self.merchant_id}"
