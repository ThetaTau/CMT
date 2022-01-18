from django.views.generic import CreateView
from .models import DepledgeSurvey


class DepledgeSurveyCreateView(CreateView):
    model = DepledgeSurvey
    success_url = "surveys:depledge"
