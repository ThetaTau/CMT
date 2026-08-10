"""Hardened wrappers around the django-report-builder views.

report_builder turns every saved filter into an ORM lookup built from the raw
string the report author typed. When that string does not fit the column, the
failure surfaces deep inside queryset iteration and returns a 500 that names
neither the report nor the filter at fault. The classic case is an ``Equals``
filter on a Postgres array column such as ``User.current_roles``, which Postgres
rejects with ``malformed array literal``.

These subclasses run the report inside a savepoint (requests are atomic, so the
outer transaction has to stay usable) and turn those failures into a 400 that
says which filter needs fixing.
"""

import logging

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import FieldError, ValidationError
from django.db import DataError, ProgrammingError, transaction
from django.shortcuts import get_object_or_404, render
from report_builder.api.views import GenerateReport
from report_builder.models import FilterField, Report
from report_builder.utils import get_model_from_path_string
from report_builder.views import DownloadFileView
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

#: Errors raised when a saved filter value does not fit the field it is set on.
#: Connection level failures are deliberately excluded so real outages still 500.
REPORT_QUERY_ERRORS = (
    DataError,
    ProgrammingError,
    FieldError,
    ValidationError,
    ValueError,
    TypeError,
)

#: Filter types Postgres can run against an array column given the plain string
#: report_builder stores. Every other type is compared as an array literal.
ARRAY_SAFE_FILTER_TYPES = frozenset(
    {
        "iexact",
        "icontains",
        "startswith",
        "istartswith",
        "endswith",
        "iendswith",
        "regex",
        "iregex",
    }
)

#: report_builder only translates these values into a real boolean.
ISNULL_SAFE_VALUES = frozenset({"0", "False"})

FILTER_TYPE_LABELS = dict(FilterField._meta.get_field("filter_type").choices)


def _model_field(report, filter_field):
    """Resolve the model field a filter points at, or None if it cannot be found."""
    try:
        model = get_model_from_path_string(report.root_model.model_class(), filter_field.path)
        return model._meta.get_field(filter_field.field)
    except Exception:  # noqa: BLE001 - diagnosis only, never worth failing on
        return None


def describe_broken_filters(report):
    """Return human readable reasons why this report's filters cannot be run."""
    problems = []
    for filter_field in report.filterfield_set.order_by("position"):
        filter_type = filter_field.filter_type or "exact"
        if filter_type in ("max", "min"):
            # Annotation filters ignore their value.
            continue
        label = filter_field.field_verbose or filter_field.field
        type_label = FILTER_TYPE_LABELS.get(filter_type, filter_type)
        if isinstance(_model_field(report, filter_field), ArrayField) and filter_type not in ARRAY_SAFE_FILTER_TYPES:
            problems.append(
                f'"{label}" holds a list of values, so the "{type_label}" filter cannot be applied to it. '
                'Use "Contains (case-insensitive)" with the value you are looking for instead.'
            )
        elif filter_type == "isnull" and filter_field.filter_value not in ISNULL_SAFE_VALUES:
            problems.append(
                f'The "Is null" filter on "{label}" only accepts a value of "False" or "0". '
                "Set the value to False or remove the filter."
            )
    return problems


def _error_context(report, exc):
    return {
        "report": report,
        "problems": describe_broken_filters(report),
        "detail": str(exc).splitlines()[0],
    }


class SafeDownloadFileView(DownloadFileView):
    """``DownloadFileView`` that explains an unrunnable filter instead of raising a 500."""

    def process_report(self, report_id, user_id, file_type, to_response, queryset=None):
        report = get_object_or_404(Report, pk=report_id)
        try:
            with transaction.atomic():
                return super().process_report(report_id, user_id, file_type, to_response, queryset)
        except REPORT_QUERY_ERRORS as exc:
            logger.warning("Report %s could not be run: %s", report_id, exc, exc_info=True)
            return render(
                self.request,
                "report_builder/report_error.html",
                _error_context(report, exc),
                status=status.HTTP_400_BAD_REQUEST,
            )


class SafeGenerateReport(GenerateReport):
    """``GenerateReport`` that returns a 400 naming the filter that cannot be run."""

    def post(self, request, report_id=None):
        report = get_object_or_404(Report, pk=report_id)
        try:
            with transaction.atomic():
                return super().post(request, report_id=report_id)
        except REPORT_QUERY_ERRORS as exc:
            logger.warning("Report %s could not be previewed: %s", report_id, exc, exc_info=True)
            context = _error_context(report, exc)
            detail = " ".join(context["problems"]) or f"This report could not be run: {context['detail']}"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
