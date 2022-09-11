from core.views import PagedFilteredTableView, LoginRequiredMixin
from .models import Invoice
from .tables import InvoiceTable, ChapterBalanceTable
from .filters import InvoiceListFilter, ChapterBalanceListFilter
from .forms import InvoiceListFormHelper, ChapterBalanceListFormHelper


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
        context["open_balance"] = Invoice.open_balance_chapter(
            chapter=self.request.user.current_chapter
        )
        return context


class ChapterBalancesListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Invoice
    context_object_name = "Invoice"
    ordering = ["chapter"]
    template_name = "finances/chapter_balances.html"
    table_class = ChapterBalanceTable
    filter_class = ChapterBalanceListFilter
    formhelper_class = ChapterBalanceListFormHelper
    table_pagination = {"per_page": 100}

    def get_queryset(self, **kwargs):
        qs = Invoice.open_balances_all().order_by("chapter")
        qs = super().get_queryset(other_qs=qs)
        return qs.filter(chapter__active=True)
