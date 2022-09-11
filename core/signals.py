from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render
from django.http import HttpResponseRedirect
from email_signals.models import Signal, SignalConstraint

CHAPTER_WATCHES = [
    ("chapters", "chapter", "id"),
    ("forms", "depledge", "user.chapter_id"),
    ("events", "event", "chapter_id"),
    ("submissions", "submission", "chapter_id"),
    ("forms", "initiation", "chapter_id"),
    ("tasks", "taskchapter", "chapter_id"),
    ("forms", "pledgeprogram", "chapter_id"),
    ("forms", "audit", "user.chapter_id"),
    ("forms", "pledge", "user.chapter_id"),
    ("forms", "chapterreport", "chapter_id"),
    ("forms", "prematurealumnus", "user.chapter_id"),
    ("forms", "pledgeprocess", "chapter_id"),
    ("forms", "initiationprocess", "chapter_id"),
    ("forms", "osm", "chapter_id"),
    ("forms", "disciplinaryprocess", "chapter_id"),
    ("forms", "collectionreferral", "user.chapter_id"),
    ("forms", "resignationprocess", "chapter_id"),
    ("forms", "pledgeprogramprocess", "chapter_id"),
    ("forms", "bylaws", "chapter_id"),
    ("forms", "hseducation", "chapter_id"),
]

USER_WATCHES = [
    ("users", "user", "id"),
    ("users", "userrolechange", "user_id"),
    ("users", "userstatuschange", "user_id"),
    ("forms", "prematurealumnus", "user_id"),
    ("forms", "disciplinaryprocess", "user_id"),
    ("forms", "collectionreferral", "user_id"),
    ("forms", "resignationprocess", "user_id"),
    ("forms", "returnstudent", "user_id"),
]


class SignalWatchMixin:
    object_type = "not_set"

    def watch_notification_add(self, request, queryset):
        if "apply" in request.POST:
            if self.object_type == "user":
                watch_types = USER_WATCHES
            else:
                watch_types = CHAPTER_WATCHES
            email = request.POST.get("emails", "central.office@thetatau.org")
            for entity in queryset:
                for watch_type in watch_types:
                    app, model, constraint_param = watch_type
                    content_type = ContentType.objects.filter(
                        app_label=app, model=model
                    ).first()
                    signal, created = Signal.objects.update_or_create(
                        name=f"{self.object_type} {entity} watch {app} {model}".title(),
                        defaults=dict(
                            name=f"{self.object_type} {entity} watch {app} {model}".title(),
                            plain_message=f"This message is to inform you that {self.object_type} {entity} watch {app} {model} was updated. In H&T, Chapter Management Tool",
                            description=f"{self.object_type} {entity} watch {app} {model}".title(),
                            content_type=content_type,
                            subject=f"{self.object_type} {entity} {app} {model} updated".title(),
                            mailing_list=email,
                            template="herald/html/signal_watch.html",
                            signal_type="post_save",
                        ),
                    )
                    if created:
                        SignalConstraint(
                            signal=signal,
                            param_1=constraint_param,
                            comparison="exact",
                            param_2=entity.id,
                        ).save()
                    else:
                        signal.mailing_list = email
                        signal.save()
            self.message_user(
                request, f"Added watch for {email} of {self.object_type}(s): {queryset}"
            )
            return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            "admin/watch_intermediate.html",
            context={"users": queryset.values_list("id", flat=True)},
        )

    watch_notification_add.short_description = "Create Notification Watch"

    def watch_notification_remove(self, request, queryset):
        if self.object_type == "user":
            watch_types = USER_WATCHES
        else:
            watch_types = CHAPTER_WATCHES
        for entity in queryset:
            for watch_type in watch_types:
                app, model, constraint_param = watch_type
                signal = Signal.objects.filter(
                    name=f"{self.object_type} {entity} watch {app} {model}".title(),
                )
                if signal:
                    signal.first().delete()
        self.message_user(
            request, f"Removed watch of {self.object_type}(s): {queryset}"
        )

    watch_notification_remove.short_description = "Remove Notification Watch"
