from dj_anonymizer.register_models import register_skip

from django_plotly_dash.models import DashApp, StatelessApp

register_skip([DashApp, StatelessApp])
