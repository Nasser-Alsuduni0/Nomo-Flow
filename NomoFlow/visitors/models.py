from django.db import models


class VisitorSession(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="visitor_sessions")
    session_id = models.CharField(max_length=64)
    started_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    device = models.CharField(max_length=40, null=True, blank=True)
    source = models.CharField(max_length=80, null=True, blank=True)
    country = models.CharField(max_length=80, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "session_id"], name="uq_session_per_merchant"),
        ]
        indexes = [
            models.Index(fields=["last_seen_at"]),
        ]
        verbose_name = "Visitor Session"
        verbose_name_plural = "Visitor Sessions"

    def __str__(self) -> str:
        return f"{self.session_id} ({self.merchant_id})"


class PageView(models.Model):
    merchant = models.ForeignKey("core.Merchant", on_delete=models.CASCADE, related_name="page_views")
    session_id = models.CharField(max_length=64)
    path = models.CharField(max_length=300)
    viewed_at = models.DateTimeField()
    referrer = models.CharField(max_length=300, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["merchant"]),
            models.Index(fields=["session_id"]),
            models.Index(fields=["merchant", "viewed_at"]),
        ]
        verbose_name = "Page View"
        verbose_name_plural = "Page Views"

    def __str__(self) -> str:
        return f"{self.path} @ {self.viewed_at}"
