import django.dispatch

# Fired after a direct (or, later, nomination) award grant is created, so
# downstream features can react without the grant path depending on them:
#   - AWI-8: generate / attach a certificate for the grant
#   - AWI-9: send notifications + create a home-page announcement
# Receivers are called with ``grant`` (the AwardGrant) and ``actor`` (the User
# who granted it), e.g. ``def receiver(sender, grant, actor, **kwargs): ...``.
award_granted = django.dispatch.Signal()
