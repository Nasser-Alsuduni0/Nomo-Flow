from django.db import models
from marketing.models import Campaign

class Rule(models.Model):
    METRICS = [("roas","ROAS"), ("cpa","CPA"), ("ctr","CTR")]
    ACTIONS = [("increase_budget","Increase Budget %"), ("pause","Pause"), ("swap_creative","Swap Creative")]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="rules")
    metric = models.CharField(max_length=16, choices=METRICS)
    comparator = models.CharField(max_length=2, default=">")    
    threshold = models.FloatField()
    action = models.CharField(max_length=32, choices=ACTIONS)
    action_value = models.FloatField(null=True, blank=True)     
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
