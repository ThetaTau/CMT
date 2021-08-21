from dj_anonymizer.register_models import register_skip

from report_builder.models import DisplayField, FilterField, Format, Report

register_skip([DisplayField, FilterField, Format, Report])
