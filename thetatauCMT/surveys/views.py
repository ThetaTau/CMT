from django.views.generic import CreateView
from .models import DepledgeSurvey


class DepledgeSurveyCreateView(CreateView):
    model = DepledgeSurvey
    success_url = "surveys:depledge"
    fields = [
        "reason",
        "reason_other",
        "decided",
        "decided_other",
        "enjoyed",
        "improve",
        "extra_notes",
        "contact",
    ]
