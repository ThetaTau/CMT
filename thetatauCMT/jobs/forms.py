from address.models import Locality
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit, Column
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton, Field
from django import forms
from tempus_dominus.widgets import DatePicker
from dal import autocomplete
from .models import Job, JobSearch
from core.forms import Select2ListCreateMultipleChoiceField, ListSelect2Multiple


class JobListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "job-search-form"
    # form_class = "form-inline"
    # field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None, natoff=False):
        extra = []
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Search For Jobs',
                Column(
                    Field("title"),
                    Field("company"),
                    Field("contact"),
                    Field("education_qualification"),
                    Field("experience"),
                    Field("job_type"),
                    Field("majors_specific"),
                    Field("location_type"),
                    # Field("zip_code"),
                    Field("country"),
                    Field("sponsored"),
                    Field("description"),
                    Field("keywords"),
                    *extra,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Search',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__(form=form)


class JobForm(forms.ModelForm):
    zip_code = Select2ListCreateMultipleChoiceField(
        label="Zip Code OR City Name",
        widget=ListSelect2Multiple(
            url="zipcode-autocomplete",
        ),
        help_text="What is the location that this job is related to.",
    )
    keywords = Select2ListCreateMultipleChoiceField(
        label="Keywords",
        help_text="Keywords to help job searchers find this job",
        widget=ListSelect2Multiple(
            url="jobs:keyword-autocomplete",
        ),
        required=False,
    )
    majors = Select2ListCreateMultipleChoiceField(
        label="Majors",
        help_text="If the job posting is for specific majors only, what are those majors?",
        widget=ListSelect2Multiple(
            url="jobs:major-autocomplete",
        ),
        required=False,
    )
    publish_start = forms.DateField(
        label="Publish Start",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    publish_end = forms.DateField(
        label="Publish End",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "company",
            "url",
            "contact",
            "education_qualification",
            "experience",
            "job_type",
            "majors_specific",
            "majors",
            "location_type",
            "zip_code",
            "country",
            "publish_start",
            "publish_end",
            "description",
            "keywords",
            "attachment",
        ]


class JobSearchForm(JobForm):
    zip_code = Select2ListCreateMultipleChoiceField(
        label="Zip Code OR City Name",
        widget=ListSelect2Multiple(
            url="zipcode-autocomplete",
        ),
        help_text="What is the location of the main office even if the job is remote.",
    )
    keywords = Select2ListCreateMultipleChoiceField(
        label="Keywords",
        help_text="Keywords to help job searchers find this job",
        widget=ListSelect2Multiple(
            url="jobs:keyword-autocomplete-ro",
        ),
        required=False,
    )
    description = forms.CharField(
        label="Description Contains",
    )
    majors = Select2ListCreateMultipleChoiceField(
        label="Majors",
        help_text="If the job posting is for specific majors only, what are those majors?",
        widget=ListSelect2Multiple(
            url="jobs:major-autocomplete",
        ),
        required=False,
    )

    class Meta:
        model = JobSearch
        fields = [
            "search_title",
            "company",
            "contact",
            "education_qualification",
            "experience",
            "job_type",
            "majors",
            "location_type",
            "zip_code",
            "country",
            "description",
            "keywords",
        ]


class JobSearchListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "job-search-form"
    # form_class = "form-inline"
    # field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None, natoff=False):
        extra = []
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Job Searches',
                Column(
                    Field("search_title"),
                    *extra,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__(form=form)
