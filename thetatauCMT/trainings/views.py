from core.views import (
    LoginRequiredMixin,
    PagedFilteredTableView,
)
from .filters import TrainingListFilter
from .forms import TrainingListFormHelper
from .models import Training
from .tables import TrainingTable


class TrainingListView(LoginRequiredMixin, PagedFilteredTableView):
    model = Training
    context_object_name = "training"
    ordering = ["-completed_time"]
    table_class = TrainingTable
    filter_class = TrainingListFilter
    formhelper_class = TrainingListFormHelper
    filter_user_chapter = True
