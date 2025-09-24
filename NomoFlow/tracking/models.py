from django.db import models
from marketing.models import Campaign

class Event(models.Model):
    KIND = [("impression","Impression"), ("click","Click"), ("conversion","Conversion"), ("spend","Spend")]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=KIND)
    value = models.FloatField(default=0)         
    meta  = models.JSONField(default=dict, blank=True)
    ts    = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [ models.Index(fields=["campaign","kind","ts"]) ]
