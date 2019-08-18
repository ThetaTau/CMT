from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.request import QueryDict
from core.views import PagedFilteredTableView, RequestConfig,\
    OfficerMixin
from .models import Transaction
from .tables import TransactionTable, ChapterBalanceTable
from .filters import TransactionListFilter, ChapterBalanceListFilter
from .forms import TransactionListFormHelper, ChapterBalanceListFormHelper


class TransactionListView(LoginRequiredMixin, OfficerMixin,
                          PagedFilteredTableView):
    model = Transaction
    context_object_name = 'transaction'
    ordering = ['-created']
    table_class = TransactionTable
    filter_class = TransactionListFilter
    formhelper_class = TransactionListFormHelper

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(chapter=self.request.user.current_chapter)

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = TransactionTable(self.get_queryset())
        RequestConfig(self.request, paginate={'per_page': 30}).configure(table)
        context['table'] = table
        context['open_balance'] = Transaction.open_balance_chapter(
            chapter=self.request.user.current_chapter)
        return context


class ChapterBalancesListView(LoginRequiredMixin, OfficerMixin,
                              PagedFilteredTableView):
    model = Transaction
    context_object_name = 'transaction'
    ordering = ['chapter']
    template_name = "finances/chapter_balances.html"
    table_class = ChapterBalanceTable
    filter_class = ChapterBalanceListFilter
    formhelper_class = ChapterBalanceListFormHelper
    table_pagination = {'per_page': 30}

    def get_queryset(self):
        qs = Transaction.open_balances_all().order_by('chapter')
        cancel = self.request.GET.get('cancel', False)
        request_get = self.request.GET.copy()
        if cancel:
            request_get = QueryDict()
        self.filter = self.filter_class(request_get, queryset=qs)
        self.filter.form.helper = self.formhelper_class()
        return self.filter.qs

    def post(self, request, *args, **kwargs):
        return PagedFilteredTableView.as_view()(request)
