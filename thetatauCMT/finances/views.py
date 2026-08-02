from core.models import user_is_national_officer
from core.views import LoginRequiredMixin, PagedFilteredTableView
from thetatauCMT.chapters.models import Chapter

from .filters import ChapterBalanceListFilter, InvoiceListFilter
from .forms import ChapterBalanceListFormHelper, InvoiceListFormHelper
from .models import Invoice, chapter_balance_overview
from .tables import ChapterBalanceTable, InvoiceTable


class InvoiceListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Invoice
    context_object_name = "invoice"
    ordering = ["-created"]
    table_class = InvoiceTable
    filter_class = InvoiceListFilter
    formhelper_class = InvoiceListFormHelper
    filter_chapter = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["open_balance"] = Invoice.open_balance_chapter(chapter=self.request.user.current_chapter)
        return context


class ChapterBalancesListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Chapter
    context_object_name = "chapters"
    ordering = ["name"]
    template_name = "finances/chapter_balances.html"
    table_class = ChapterBalanceTable
    filter_class = ChapterBalanceListFilter
    formhelper_class = ChapterBalanceListFormHelper
    table_pagination = {"per_page": 100}

    def get_queryset(self, **kwargs):
        qs = chapter_balance_overview().order_by("name")
        # An ordinary member sees only their own chapter's balance; National
        # Officers and admins see every chapter.
        if not user_is_national_officer(self.request.user):
            chapter = self.request.user.current_chapter
            qs = qs.filter(pk=chapter.pk) if chapter else qs.none()
        qs = super().get_queryset(other_qs=qs)
        return qs
