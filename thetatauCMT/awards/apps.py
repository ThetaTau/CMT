from django.apps import AppConfig


class AwardsConfig(AppConfig):
    name = "thetatauCMT.awards"
    verbose_name = "Awards"

    def ready(self):
        from .receivers import notify_on_award_granted, on_award_granted
        from .signals import award_granted

        award_granted.connect(on_award_granted, dispatch_uid="awards.auto_certificate")
        award_granted.connect(notify_on_award_granted, dispatch_uid="awards.grant_notification")
