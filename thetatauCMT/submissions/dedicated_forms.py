"""Score types whose submission comes from their own form, never from an upload.

Each of these forms records the chapter's submission itself and does the rest of
its job (the Gear editor gets the article, the new member education program goes
to review, ...). An upload on "Add a submission" skipped all of that and could
claim points the real form decides, so that page points to the form instead.
Keyed by the stable ``ScoreType.slug`` from scores/fixtures/scoretypes.json.
"""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class DedicatedForm:
    url_name: str
    form_name: str
    reason: str

    @property
    def url(self):
        return reverse(self.url_name)


DEDICATED_FORMS = {
    "article": DedicatedForm(
        url_name="submissions:gear",
        form_name="Gear article form",
        reason="It sends your article and photos to the Gear editor and records it in your chapter's submissions.",
    ),
    "audit": DedicatedForm(
        url_name="forms:audit",
        form_name="chapter audit form",
        reason="Completing the audit records it in your chapter's submissions.",
    ),
    "pledge-program": DedicatedForm(
        url_name="viewflow:forms:pledgeprogramprocess:start",
        form_name="new member education program form",
        reason="It sends your program for review and records it in your chapter's submissions.",
    ),
    "osm": DedicatedForm(
        url_name="viewflow:forms:osm:start",
        form_name="outstanding student member form",
        reason="It sends your nomination and records it in your chapter's submissions.",
    ),
    "rmp": DedicatedForm(
        url_name="forms:rmp",
        form_name="risk management policies form",
        reason="Each member signs the policies there, and every signature is recorded in their chapter's submissions.",
    ),
}


def dedicated_form_for(score_type):
    """The form that replaces uploads for ``score_type`` (a ScoreType or its slug), or None."""
    return DEDICATED_FORMS.get(getattr(score_type, "slug", score_type))
