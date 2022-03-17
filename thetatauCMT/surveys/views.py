from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic import CreateView
from users.models import User
from .models import DepledgeSurvey
from .forms import DepledgeSurveyForm
from .notifications import DepledgeSurveyFollowUpEmail


class DepledgeSurveyCreateView(CreateView):
    model = DepledgeSurvey
    slug_url_kwarg = "user_id"
    slug_field = "user__user_id"
    form_class = DepledgeSurveyForm

    def get_success_url(self):
        return reverse("surveys:depledge", kwargs={"user_id": self.kwargs["user_id"]})

    def form_valid(self, form):
        self.object = form.save(commit=False)
        user_id = self.kwargs.get(self.slug_url_kwarg)
        user = User.objects.get(user_id=user_id)
        self.object.user = user
        self.object.save()
        if self.object.contact:
            link = reverse(
                "admin:surveys_depledgesurvey_change",
                kwargs={"object_id": self.object.id},
            )
            message = mark_safe(
                f"A depledge from {user.chapter.full_name} has asked "
                f"for a follow up to their survey. <br>"
                f'<a href="{settings.CURRENT_URL}{link}">See link here.</a>'
            )
            DepledgeSurveyFollowUpEmail(user.id, message).send()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get(self.slug_url_kwarg)
        context["user"] = None
        context["depledge"] = None
        context["user_id"] = user_id
        try:
            # Verify that user exists
            user = User.objects.get(user_id=user_id)
            context["user"] = user
        except User.DoesNotExist:
            pass
        else:
            queryset = self.get_queryset()
            try:
                # Verify that the user has been depledged
                context["depledge"] = user.depledge
            except User.depledge.RelatedObjectDoesNotExist:
                pass
            else:
                try:
                    context["object"] = queryset.get(user__user_id=user_id)
                except queryset.model.DoesNotExist:
                    pass
        return context