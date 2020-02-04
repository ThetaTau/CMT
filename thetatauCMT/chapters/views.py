from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.forms.models import modelformset_factory
from django.http.response import HttpResponseRedirect
from django.views.generic import RedirectView
from core.views import RequestConfig, OfficerMixin, OfficerRequiredMixin,\
    PagedFilteredTableView
from core.forms import MultiFormsView
from core.models import TODAY_START, forever
from .models import Chapter
from .forms import ChapterForm, ChapterFormHelper
from .filters import ChapterListFilter
from .tables import ChapterCurriculaTable, ChapterTable, AuditTable
from users.tables import UserTable
from users.models import UserStatusChange, User
from users.forms import ExternalUserForm
from tasks.models import Task
from submissions.models import Submission
from forms.notifications import EmailAdvisorWelcome


class ChapterDetailView(LoginRequiredMixin, OfficerMixin, MultiFormsView):
    template_name = 'chapters/chapter_detail.html'
    form_classes = {
        'chapter': ChapterForm,
        'faculty': ExternalUserForm,
    }

    def faculty_form_valid(self, formset):
        if formset.has_changed():
            for form in formset.forms:
                if form.changed_data and 'DELETE' not in form.changed_data:
                    chapter = self.request.user.current_chapter
                    if form.instance.badge_number == 999999999:
                        form.instance.chapter = chapter
                        form.instance.badge_number = chapter.next_advisor_number
                    try:
                        # This is either a previous faculty or alumni
                        user = User.objects.get(username=form.instance.email)
                    except User.DoesNotExist:
                        user = form.save()
                    try:
                        status = UserStatusChange.objects.get(user=user).first()
                    except UserStatusChange.DoesNotExist:
                        UserStatusChange(
                            user=user,
                            status='advisor',
                            start=TODAY_START,
                            end=forever(),
                        ).save()
                        EmailAdvisorWelcome(user).send()
                elif form.changed_data and 'DELETE' in form.changed_data:
                    user = form.instance
                    try:
                        status = UserStatusChange.objects.get(user=user)
                    except UserStatusChange.DoesNotExist:
                        continue
                    else:
                        status.end = TODAY_START
                        status.save()
        return HttpResponseRedirect(self.get_success_url())

    def create_faculty_form(self, **kwargs):
        chapter = self.request.user.current_chapter
        facultys = chapter.advisors_external
        extra = 0
        min_num = 0
        if not facultys:
            extra = 0
            min_num = 1
        factory = modelformset_factory(
            User,
            form=ExternalUserForm,
            **{
                'can_delete': True,
                'extra': extra,
                'min_num': min_num,
                'validate_min': True,
            })
        # factory.form.base_fields['chapter'].queryset = chapter
        formset_kwargs = {
            'queryset': facultys,
            'form_kwargs': {
                'initial': {'chapter': chapter}
            }
        }
        if self.request.method in ('POST', 'PUT'):
            formset_kwargs.update({
                'data': self.request.POST.copy(),
            })
        return factory(**formset_kwargs)

    def get_success_url(self, form_name=None):
        return reverse('chapters:detail',
                       kwargs={'slug': self.kwargs['slug']})

    def chapter_form_valid(self, form):
        if form.has_changed():
            form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_tasks = Task.objects.filter(name="Audit")
        chapter = self.request.user.current_chapter
        audit_items = [
            'user',
            'modified',
            'dues_member',
            'dues_pledge',
            'frequency',
            'payment_plan',
            'cash_book',
            'cash_book_reviewed',
            'cash_register',
            'cash_register_reviewed',
            'member_account',
            'member_account_reviewed',
            'balance_checking',
            'balance_savings',
            'debit_card',
            'debit_card_access',]
        audit_data = [{"item": item} for item in audit_items]
        for task in audit_tasks:
            complete = task.completed_last(chapter=chapter)
            if type(complete) is Submission:
                complete = None
            if complete:
                [item.update(
                    {task.owner.replace(' ', '_'): getattr(complete,
                                                           item['item'])})
                 for item in audit_data]
            else:
                [item.update({task.owner.replace(' ', '_'): "Incomplete"})
                 for item in audit_data]
        [item.update({'item': item['item'].replace('_', ' ').title()})
         # {
         #     'item': 'Debit Card Access',
         #     'corresponding_secretary': 'Incomplete',
         #     'treasurer': ['regent', 'treasurer'],
         #     'scribe': 'Incomplete',
         #     'vice_regent': ['regent', 'treasurer'],
         #     'regent': ['regent', 'treasurer']
         # }
         for item in audit_data]
        audit_table = AuditTable(data=audit_data)
        RequestConfig(self.request).configure(audit_table)
        context['audit_table'] = audit_table
        chapter = self.get_object()
        context.update({
            "object": chapter,
        })
        chapter_officers, previous = chapter.get_current_officers()
        table = UserTable(data=chapter_officers)
        table.exclude = ('badge_number', 'graduation_year')
        RequestConfig(self.request, paginate={'per_page': 100}).configure(table)
        context['table'] = table
        majors = chapter.curricula.all().order_by('major')
        major_table = ChapterCurriculaTable(data=majors)
        context['majors'] = major_table
        email_list = ', '.join([x.email for x in chapter_officers])
        context['email_list'] = email_list
        context['previous_officers'] = previous
        return context

    def get_form_kwargs(self, form_name, bind_form=False):
        kwargs = super().get_form_kwargs(form_name, bind_form)
        if form_name == 'chapter':
            kwargs.update(
                {'instance': self.get_object(),
                 }
            )
        return kwargs

    def get_object(self):
        # Only get the User record for the user making the request
        return Chapter.objects.get(slug=self.kwargs['slug'])


class ChapterRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self):
        return reverse('chapters:detail',
                       kwargs={'slug': self.request.user.current_chapter.slug})


class ChapterListView(OfficerRequiredMixin,
                      LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    model = Chapter
    context_object_name = 'chapter'
    ordering = ['name']
    table_class = ChapterTable
    filter_class = ChapterListFilter
    formhelper_class = ChapterFormHelper
    table_pagination = False

    def get_table_kwargs(self):
        return {
            'officer': self.request.user.is_national_officer(),
        }
