"""Template context for the unprompted What's New modal (TWI-6).

This runs on every rendered page, so the cheap disqualifiers in
:func:`~thetatauCMT.guides.services.whats_new_modal_allowed` come first and the
feed query only happens when a modal could actually appear. Once the modal has
been shown -- or once we know there is nothing to show -- a session key short
circuits the whole thing for the rest of the session.
"""

from django.conf import settings

from . import services


def whats_new(request):
    """``{"whats_new_modal": {...}}`` when this request should offer the modal."""
    if not services.whats_new_modal_allowed(request):
        return {}
    items = services.get_whats_new(request.user)
    if not items:
        # Nothing to say. Remember that, otherwise every page of this session
        # pays for the same empty feed.
        request.session[services.WHATS_NEW_SESSION_KEY] = True
        return {}
    cap = settings.WHATS_NEW_MAX_ITEMS
    return {
        "whats_new_modal": {
            "items": items[:cap],
            "total": len(items),
            "has_more": len(items) > cap,
        }
    }
