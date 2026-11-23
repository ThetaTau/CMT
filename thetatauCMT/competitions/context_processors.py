"""Menu links for the Case Competition (S24, S25; Gotchas 11).

Every value is lazy, so pages that never draw the menu run no query, and each is worked out
at most once per request.
"""

from django.utils.functional import SimpleLazyObject


def case_competition(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    def published():
        from .models import Competition

        return Competition.objects.published().only("slug", "name", "year_label").first()

    def judging():
        from .judging import judges_anything

        return judges_anything(user)

    judges = SimpleLazyObject(judging)

    def to_do():
        from .judging import ScorecardsToDo, scorecards_to_do

        # Only judges pay for the count; everyone else stops at the one query in judging().
        return scorecards_to_do(user) if judges else ScorecardsToDo()

    return {
        "case_competition": SimpleLazyObject(published),
        "case_competition_judging": judges,
        "case_competition_to_do": SimpleLazyObject(to_do),
    }
