import codecs

from django.contrib import admin
from core.admin import user_chapter
from django.http import HttpResponse
from import_export.admin import ExportActionModelAdmin
from survey.admin import (
    Survey as Survey_orig,
    SurveyAdmin,
    Response,
    ResponseAdmin,
    make_published,
    Survey2Csv,
    Survey2Tex,
)
from .models import DepledgeSurvey, Survey

EXCEL_COMPATIBLE_CSV = False


class DepledgeSurveyAdmin(ExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "user",
        user_chapter,
        "reason",
        "decided",
        "created",
    )
    list_filter = [
        "decided",
        "contact",
        "reason",
        "created",
        "user__chapter",
    ]
    search_fields = ("user__name", "user__username")
    ordering = [
        "-created",
    ]


class Survey2CsvUpdated(Survey2Csv):
    def __str__(self):
        csv = []
        if EXCEL_COMPATIBLE_CSV:
            csv.append(self.EXCEL_HACK)
        header, question_order = self.get_header_and_order()
        header = ["created", "updated"] + header
        csv.append(Survey2Csv.line_list_to_string(header))
        for response in self.survey.responses.all():
            line = Survey2Csv.get_user_line(question_order, response)
            line = [
                response.created.strftime("%Y-%m-%d %H:%M:%S"),
                response.updated.strftime("%Y-%m-%d %H:%M:%S"),
            ] + line
            csv.append(Survey2Csv.line_list_to_string(line))
        return "\n".join(csv)

    @staticmethod
    def export_as_csv(modeladmin, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response.write(codecs.BOM_UTF8)
        filename = ""
        for i, survey in enumerate(queryset):
            survey_as_csv = Survey2CsvUpdated(survey)
            if i == 0:
                filename = survey.safe_name
            if len(queryset) == 1:
                response.write(survey_as_csv)
            else:
                if EXCEL_COMPATIBLE_CSV:
                    survey_as_csv = str(survey_as_csv).replace(
                        f"{Survey2Csv.EXCEL_HACK}\n", ""
                    )
                if i != 0:
                    filename += f"-{survey.safe_name}"
                elif EXCEL_COMPATIBLE_CSV:
                    # If we need to be compatible with excel and it's the first survey
                    response.write(f"{Survey2Csv.EXCEL_HACK}\n")
                response.write(f"{survey.name}\n")
                response.write(survey_as_csv)
                response.write("\n\n")
        response["Content-Disposition"] = f"attachment; filename={filename}.csv"
        return response


class SurveyAdminUpdated(SurveyAdmin):
    actions = [
        make_published,
        Survey2CsvUpdated.export_as_csv,
        Survey2Tex.export_as_tex,
    ]


admin.site.register(DepledgeSurvey, DepledgeSurveyAdmin)

admin.site.unregister(Survey_orig)
admin.site.register(Survey, SurveyAdminUpdated)

admin.site.unregister(Response)
admin.site.register(Response, ResponseAdmin)
