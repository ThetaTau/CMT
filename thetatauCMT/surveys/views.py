from datetime import date
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import redirect, Http404
from django.utils.safestring import mark_safe
from django.views.generic import CreateView
from users.models import User
from .models import DepledgeSurvey, Survey
from .forms import DepledgeSurveyForm, ResponseForm
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


class SurveyDetail(CreateView):
    # Override the function:
    #   from survey.views import SurveyDetail
    model = Survey
    template_name = "surveys/base_survey.html"
    template_name_field = "template"
    form_class = ResponseForm
    data = None
    step = None

    def get_object(self, queryset=None):
        survey = super().get_object()
        if not survey.is_published:
            raise Http404
        if survey.expire_date < date.today():
            messages.warning(
                self.request,
                f"Survey is not published anymore. It was published until: '{survey.expire_date}'.",
            )
            return redirect(reverse("home"))
        if survey.publish_date > date.today():
            messages.warning(
                self.request,
                f"Survey is not yet published. It is due: '{survey.publish_date}'.",
            )
            raise Http404
        return survey

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "survey": self.object,
                "user": self.request.user,
            }
        )
        if self.step is not None:
            kwargs["step"] = self.step
        return kwargs

    def get(self, request, *args, **kwargs):
        self.step = kwargs.get("step", 0)
        self.object = self.get_object()
        if self.object.need_logged_user and not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if not self.object.editable_answers:
            self.step = None
            self.object.display_method = 0
        return self.render_to_response(self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        categories = form.current_categories()
        asset_context = {
            # If any of the widgets of the current form has a "date" class, flatpickr will be loaded into the
            # template
            "flatpickr": any(
                [
                    field.widget.attrs.get("class") == "date"
                    for _, field in form.fields.items()
                ]
            )
        }
        context.update(
            **{
                "response_form": form,
                "survey": self.object,
                "categories": categories,
                "step": self.step,
                "asset_context": asset_context,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        self.step = kwargs.get("step", 0)
        self.object = self.get_object()
        if self.object.need_logged_user and not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        form = self.get_form()
        if not self.object.editable_answers and form.response is not None:
            messages.warning(self.request, f"Survey is not editable.")
            return redirect(self.request.path, slug=self.object.slug)
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        session_key = f"survey_{self.object.id}"
        if session_key not in self.request.session:
            self.request.session[session_key] = {}
        for key, value in list(form.cleaned_data.items()):
            self.request.session[session_key][key] = value
            self.request.session.modified = True
        next_url = form.next_step_url()
        response = None
        if self.object.is_all_in_one_page():
            response = form.save()
        else:
            # when it's the last step
            if not form.has_next_step():
                self.step = None
                kwargs = self.get_form_kwargs()
                kwargs["data"] = self.request.session[session_key]
                save_form = self.get_form_class()(**kwargs)
                if save_form.is_valid():
                    response = save_form.save()
                else:
                    messages.error(
                        self.request,
                        f"A step of the multipage form failed. "
                        f"If this issue persists, please reach out to us.",
                    )
        # if there is a next step
        if next_url is not None:
            return redirect(next_url)
        del self.request.session[session_key]
        if response is None:
            messages.error(
                self.request,
                f"There was an error submitting the form.",
            )
            return redirect("surveys:survey-detail", slug=self.object.slug)
        next_ = self.request.session.get("next", None)
        if next_ is not None:
            if "next" in self.request.session:
                del self.request.session["next"]
            return redirect(next_)
        message = "Thanks! Your answers have been saved"
        new_location = redirect("surveys:survey-detail", slug=self.object.slug)
        if self.object.editable_answers:
            message += "<br>The survey is editable after submission, so you can always come back and change them."
        if self.object.redirect_url:
            new_location = redirect(self.object.redirect_url)
        messages.info(self.request, mark_safe(message))
        return new_location
