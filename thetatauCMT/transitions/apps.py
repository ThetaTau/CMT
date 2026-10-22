from django.apps import AppConfig
from watson import search as watson


class TransitionsConfig(AppConfig):
    name = "thetatauCMT.transitions"
    verbose_name = "Transition Reports"

    def ready(self):
        """TRWI-11: register submitted ``TransitionReport``s for full-text
        search. Registers a QUERYSET (``status="submitted"`` only), not the
        bare model -- mirrors ``jobs.apps.JobsConfig``'s
        ``model.get_live_jobs()`` pattern -- so a draft is never indexed,
        let alone returned, by search, matching ``services.search_reports``'
        own submitted-only restriction (belt-and-suspenders: even if a caller
        someday queries the watson index directly, drafts still can't appear).

        ``answers__value`` walks the reverse ``ReportAnswer.report`` relation
        (``related_name="answers"``) -- watson's ``SearchAdapter._resolve_field``
        detects the related manager and joins every answer's text automatically,
        so the FULL body of the report is indexed, not just its own fields.
        ``contacts__name``/``contacts__notes``/``key_dates__label``/
        ``key_dates__timing`` (2026-09 structured-content pass, TRWI-13
        proposal) use the exact same reverse-relation-traversal mechanism, so
        the new structured Contacts/Key Dates content is fully searchable
        from day one with no dedicated search UI of its own needed for v1.
        When this is updated need to run: python manage.py buildwatson
        """
        model = self.get_model("TransitionReport")
        watson.register(
            model.objects.filter(status="submitted"),
            fields=[
                "position_key",
                "answers__value",
                "chapter__name",
                "author__name",
                "contacts__name",
                "contacts__notes",
                "key_dates__label",
                "key_dates__timing",
            ],
        )
