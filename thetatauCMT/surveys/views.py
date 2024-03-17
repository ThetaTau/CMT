import base64
from datetime import date
from django.db import IntegrityError, transaction
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import redirect, Http404
from django.utils.safestring import mark_safe
from django.views.generic import CreateView
from users.models import User
from .models import DepledgeSurvey, Survey
from .forms import DepledgeSurveyForm, ResponseForm
from .notifications import SurveyFollowUpEmail


class DepledgeSurveyCreateView(CreateView):
    model = DepledgeSurvey
    slug_url_kwarg = "username"
    slug_field = "user__username"
    form_class = DepledgeSurveyForm

    def get_success_url(self):
        return reverse("surveys:depledge", kwargs={"username": self.kwargs["username"]})

    def form_valid(self, form):
        self.object = form.save(commit=False)
        username = self.kwargs.get(self.slug_url_kwarg)
        user = User.objects.get(username=username)
        self.object.user = user
        try:
            with transaction.atomic():
                self.object.save()
        except IntegrityError:
            messages.add_message(
                self.request,
                messages.ERROR,
                mark_safe(
                    f"Survey already submitted for {user}<br>"
                    f"If you have additional information you would like to provide<br> "
                    f"please message central.office@thetatau.org"
                ),
            )
            return super().form_invalid(form)
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
            SurveyFollowUpEmail(user.id, message).send()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        username = self.kwargs.get(self.slug_url_kwarg)
        context["user"] = None
        context["depledge"] = None
        context["username"] = username
        try:
            # Verify that user exists
            user = User.objects.get(username=username)
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
                    context["object"] = queryset.get(user__username=username)
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
    user = None
    user_pk = None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "instance": None,
                "survey": self.object,
                "user": self.user,
                "user_pk": self.user_pk,
            }
        )
        if self.step is not None:
            kwargs["step"] = self.step
        return kwargs

    def get_user(self, request, kwargs):
        user_pk_encoded = kwargs.get("user_pk", None)
        self.user = request.user
        if user_pk_encoded is not None and user_pk_encoded not in ("anonymous", "None"):
            try:
                user_pk_decoded = base64.b64decode(user_pk_encoded).decode("utf-8")
                self.user = User.objects.get(id=user_pk_decoded)
            except Exception as e:
                messages.error(
                    request,
                    f"Error finding member. "
                    f"Make sure you have the correct survey link",
                )
            else:
                self.user_pk = user_pk_encoded
                if request.method == "GET":
                    messages.info(
                        request,
                        mark_safe(
                            f"Filling out the survey for {self.user}<br>"
                            f"If that is not you, please verify your link or log in."
                        ),
                    )

    def dispatch(self, request, *args, **kwargs):
        self.step = kwargs.get("step", 0)
        self.get_user(request, kwargs)
        self.object = self.get_object()
        message = None
        location = None
        if not self.object.is_published:
            message = f"Survey is not available to complete."
            location = redirect(reverse("home"))
        elif self.object.publish_date > date.today():
            message = (
                f"Survey is not yet published. It is due: '{self.object.publish_date}'."
            )
            location = redirect(reverse("home"))
        elif self.object.expire_date < date.today():
            message = f"Survey is not published anymore. It was published until: '{self.object.expire_date}'."
            location = redirect(reverse("home"))
        elif self.object.need_logged_user and not request.user.is_authenticated:
            message = f"You must log in to access the survey"
            location = redirect(
                f"{settings.CURRENT_URL}/accounts/login?next={request.path}"
            )
        elif not self.object.anonymous and self.user.is_anonymous:
            # If the survey does not allow anonymous and the found user is anonymous
            message = (
                f"Make sure you have your unique link to fill out the survey, "
                f"or log in to fill out the survey."
            )
            location = redirect(
                f"{settings.CURRENT_URL}/accounts/login?next={request.path}"
            )
        elif self.object.need_logged_user and self.user != request.user:
            # If the survey needs logged user and the current user is not the found user
            #   above already checked logged in
            message = f"You can not submit the survey for others"
            location = redirect("surveys:survey-detail", slug=self.object.slug)
        elif (
            self.object.anonymous
            and self.user.is_anonymous
            and self.user == request.user
        ):
            # If the survey does allow anonymous and the found user is anonymous
            message = f"You are filling out this survey anonymously."
        if message is not None and request.method == "GET":
            messages.warning(request, message)
        if location is not None:
            return location
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
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
        user_pk = "anonymous"
        if not self.user.is_anonymous:
            user_pk = base64.b64encode(str(self.user.id).encode("utf-8")).decode(
                "utf-8"
            )
        step = self.step
        if self.step is None:
            step = 0
        percent = int(round(100 * ((1 + step) / form.steps_count), 0))
        context.update(
            **{
                "response_form": form,
                "survey": self.object,
                "categories": categories,
                "step": self.step,
                "asset_context": asset_context,
                "user_pk": user_pk,
                "percent": percent,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
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
        complete = False
        if self.object.is_all_in_one_page():
            response = form.save()
            complete = True
        else:
            # when it's the last step
            if not form.has_next_step():
                self.step = None
                kwargs = self.get_form_kwargs()
                kwargs["data"] = self.request.session[session_key]
                save_form = self.get_form_class()(**kwargs)
                if save_form.is_valid():
                    response = save_form.save()
                    complete = True
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
        new_location = redirect(
            "surveys:survey-detail-member", slug=self.object.slug, user_pk=self.user_pk
        )
        if self.object.editable_answers and not self.user.is_anonymous:
            message += "<br>The survey is editable after submission, so you can always come back and change them."
        if self.object.redirect_url:
            new_location = redirect(self.object.redirect_url)
        messages.info(self.request, mark_safe(message))
        if complete:
            answer = response.answers.filter(
                question__text__icontains="to contact you"
            ).first()
            if answer and answer.body == "yes":
                link = new_location.url
                if "http" not in link:
                    link = f"{settings.CURRENT_URL}{link}"
                message = mark_safe(
                    f"A member from {self.user.chapter.full_name} has asked "
                    f"for a follow up to their {self.object.name} survey. <br>"
                    f'<a href="{link}">See link here.</a>'
                )
                SurveyFollowUpEmail(self.user.id, message).send()
        return new_location
