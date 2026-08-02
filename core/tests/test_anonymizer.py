"""Every project model is registered with the anonymizer.

``anonymize_db`` refuses to run if a single model is missing from one of the
skip / clean / anonym lists, which is the right behaviour -- but it is a
management command nobody runs while building a feature, so a whole new app can
land with no ``anonymizer/<app>.py`` and nothing says a word until someone tries
to refresh staging. That is exactly how ``guides`` slipped through. This test
turns that silence into a failing build.

``dj_anonymizer`` is deliberately absent from ``INSTALLED_APPS`` outside local /
staging, so the management command cannot be called here. ``Anonymizer`` itself
does not need the app installed: it walks ``apps.get_app_configs()`` and imports
``anonymizer.base`` plus one module per app, then raises ``LookupError`` naming
whatever it could not account for.
"""

import pytest


@pytest.mark.django_db  # register_clean introspects the table list
def test_every_model_is_registered_with_the_anonymizer():
    """A new app needs an ``anonymizer/<app>.py`` before it is done."""
    from dj_anonymizer.anonymizer import Anonymizer

    Anonymizer(soft_mode=False)
