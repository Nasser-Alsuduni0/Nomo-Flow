from django.db import models

class Campaign(models.Model):
    OBJ = [("sales","Increase Sales"), ("awareness","Brand Awareness"), ("clearance","Clearance")]
    CH  = [("tiktok","TikTok"), ("instagram","Instagram"), ("snapchat","Snapchat")]

    name = models.CharField(max_length=200)
    objective = models.CharField(max_length=32, choices=OBJ, default="sales")
    product_url = models.URLField()
    budget_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    primary_channel = models.CharField(max_length=32, choices=CH, default="tiktok")
    status = models.CharField(max_length=20, default="draft")   
    external_ids = models.JSONField(default=dict, blank=True)
    start_at = models.DateTimeField(auto_now_add=True)
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.name
