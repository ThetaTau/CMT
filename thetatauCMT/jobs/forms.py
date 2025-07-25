from address.models import Country, Locality
from crispy_forms.bootstrap import Field, FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Fieldset, Layout, Row, Submit
from django import forms
from tempus_dominus.widgets import DatePicker

from core.forms import (
    ListSelect2Multiple,
    Select2ListCreateMultipleChoiceField,
    set_multiple_choices_initial,
)

from .models import Job, JobSearch, Keyword, Major


class JobListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "job-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None, natoff=False):
        extra = []
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Quick Filter Jobs',
                Row(
                    InlineField("text_search"),
                    InlineField("education_qualification"),
                    InlineField("experience"),
                    InlineField("job_type"),
                    InlineField("contact"),
                    InlineField("location_type"),
                    *extra,
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-filter"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear Quick Filter", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__(form=form)


class JobForm(forms.ModelForm):
    location = Select2ListCreateMultipleChoiceField(
        label="Zip Code OR City Name",
        queryset=Locality.objects.all(),
        widget=ListSelect2Multiple(
            url="zipcode-autocomplete",
        ),
        help_text="What is the location that this job is related to.",
    )
    keywords = Select2ListCreateMultipleChoiceField(
        label="Keywords",
        queryset=Keyword.objects.all(),
        help_text="Keywords to help job searchers find this job",
        widget=ListSelect2Multiple(
            url="jobs:keyword-autocomplete",
        ),
        required=False,
    )
    majors = Select2ListCreateMultipleChoiceField(
        label="Majors",
        queryset=Major.objects.all(),
        help_text="If the job posting is for specific majors only, what are those majors?",
        widget=ListSelect2Multiple(
            url="jobs:major-autocomplete",
        ),
        required=False,
    )
    publish_start = forms.DateField(
        label="Job Post Date",
        help_text="When should this job be published and visible to members?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    publish_end = forms.DateField(
        label="Job Post Removal Date",
        help_text="When should this job be removed and no longer visible to members?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    # country = forms.ModelChoiceField(
    #     queryset=Country.objects.all(),
    #     initial=Country.objects.get(name="United States"),
    #     help_text="What country is this job posting for?",
    # )

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
            "location",
            "country",
            "publish_start",
            "publish_end",
            "description",
            "keywords",
            "attachment",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            set_multiple_choices_initial(self, "keywords")
            set_multiple_choices_initial(self, "majors")
            set_multiple_choices_initial(self, "location")


class JobSearchFormHelper(FormHelper):
    form_method = "GET"
    form_id = "job-search-form"
    # form_class = "form-inline"
    # field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            "",
            Column(
                Field("search_title"),
                Field("search_description"),
                Field("notification"),
                Row(
                    Field("title_filter"),
                    Field("title"),
                ),
                Row(
                    Field("description_filter"),
                    Field("description"),
                ),
                Row(
                    Field("company_filter"),
                    Field("company"),
                ),
                Row(
                    Field("contact_filter"),
                    Field("contact"),
                ),
                Row(
                    Field("education_filter"),
                    Field("education_qualification"),
                ),
                Row(
                    Field("experience_filter"),
                    Field("experience"),
                ),
                Row(
                    Field("job_type_filter"),
                    Field("job_type"),
                ),
                Row(
                    Field("majors_filter"),
                    Field("majors"),
                ),
                Row(
                    Field("location_type_filter"),
                    Field("location_type"),
                ),
                Row(
                    Field("location_filter"),
                    Field("location"),
                ),
                Row(
                    Field("country_filter"),
                    Field("country"),
                ),
                Row(
                    Field("keywords_filter"),
                    Field("keywords"),
                ),
                FormActions(
                    StrictButton(
                        '<i class="fa fa-times"></i> Cancel',
                        type="button",
                        css_class="btn-danger",
                        onclick="window.history.back();",
                    ),
                    StrictButton(
                        '<i class="fa fa-save"></i> Save',
                        type="save",
                        css_class="btn-warning",
                    ),
                ),
            ),
        ),
    )


class JobSearchForm(forms.ModelForm):
    location = Select2ListCreateMultipleChoiceField(
        label="Zip Code OR City Name",
        queryset=Locality.objects.all(),
        widget=ListSelect2Multiple(
            url="zipcode-autocomplete",
        ),
        help_text="What is the location of the main office even if the job is remote.",
        required=False,
    )
    keywords = Select2ListCreateMultipleChoiceField(
        label="Keywords",
        queryset=Keyword.objects.all(),
        help_text="Keywords to help job searchers find this job",
        widget=ListSelect2Multiple(
            url="jobs:keyword-autocomplete",
        ),
        required=False,
    )
    majors = Select2ListCreateMultipleChoiceField(
        label="Majors",
        queryset=Major.objects.all(),
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
            "search_description",
            "notification",
            "title_filter",
            "title",
            "description_filter",
            "description",
            "company_filter",
            "company",
            "contact_filter",
            "contact",
            "education_filter",
            "education_qualification",
            "experience_filter",
            "experience",
            "job_type_filter",
            "job_type",
            "majors_filter",
            "majors",
            "location_type_filter",
            "location_type",
            "location_filter",
            "location",
            "country_filter",
            "country",
            "keywords_filter",
            "keywords",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = JobSearchFormHelper()
        if self.instance.id:
            set_multiple_choices_initial(self, "keywords")
            set_multiple_choices_initial(self, "majors")
            set_multiple_choices_initial(self, "location")


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
                '<i class="fas fa-search"></i> Quick Filter Job Searches',
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
