from django.http import JsonResponse
from .tasks import automate_campaigns

def run_automation(request):
    automate_campaigns()
    return JsonResponse({"message": "Automation executed successfully"})
