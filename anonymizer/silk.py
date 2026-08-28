from dj_anonymizer.register_models import register_skip
from silk.models import Profile, Request, Response, SQLQuery

# django-silk (staging-only profiler): staging data itself, so no need to clean.
register_skip([Request, Response, SQLQuery, Profile])
