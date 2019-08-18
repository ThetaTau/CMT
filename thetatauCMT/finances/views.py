from django.contrib.auth.mixins import LoginRequiredMixin
from core.views import PagedFilteredTableView, RequestConfig,\
    OfficerMixin
from .models import Transaction
from .tables import TransactionTable
from .filters import TransactionListFilter
from .forms import TransactionListFormHelper


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
