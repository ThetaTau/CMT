from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.request import QueryDict
from core.views import PagedFilteredTableView, RequestConfig, OfficerMixin
from .models import Transaction
from .tables import TransactionTable, ChapterBalanceTable
from .filters import TransactionListFilter, ChapterBalanceListFilter
from .forms import TransactionListFormHelper, ChapterBalanceListFormHelper


class TransactionListView(LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    model = Transaction
    context_object_name = "transaction"
    ordering = ["-created"]
    table_class = TransactionTable
    filter_class = TransactionListFilter
    formhelper_class = TransactionListFormHelper
    filter_chapter = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["open_balance"] = Transaction.open_balance_chapter(
            chapter=self.request.user.current_chapter
        )
        return context


class ChapterBalancesListView(LoginRequiredMixin, OfficerMixin, PagedFilteredTableView):
    model = Transaction
    context_object_name = "transaction"
    ordering = ["chapter"]
    template_name = "finances/chapter_balances.html"
    table_class = ChapterBalanceTable
    filter_class = ChapterBalanceListFilter
    formhelper_class = ChapterBalanceListFormHelper
    table_pagination = {"per_page": 30}

    def get_queryset(self, **kwargs):
        qs = Transaction.open_balances_all().order_by("chapter")
        qs = super().get_queryset(other_qs=qs)
        return qs
