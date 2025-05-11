from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton, Field
from dal import autocomplete, forward
from .models import Picture, GearArticle
from users.models import User


class SubmissionListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "submission-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Submissions',
            Row(
                InlineField("name"),
                InlineField("date"),
                InlineField("type"),
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


class PictureForm(forms.ModelForm):
    image = forms.ImageField()
    description = forms.CharField(
        help_text="Include name of person who took the photo as well as a brief description.",
        widget=forms.Textarea(),
    )

    class Meta:
        model = Picture
        fields = [
            "description",
            "image",
        ]


class GearArticleForm(forms.ModelForm):
    name = forms.CharField(label="Article Title")
    file = forms.FileField(
        required=False,
        help_text="You can optionally attach your article or supporting documents",
    )
    authors = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=autocomplete.ModelSelect2Multiple(
            url="users:autocomplete", forward=(forward.Const("true", "chapter"),)
        ),
    )

    class Meta:
        model = GearArticle
        fields = [
            "name",
            "authors",
            "article",
            "file",
        ]


class GearArticleListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "gear-article-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            "",
            Row(
                Field("region"),
                Field("chapter"),
                Field("reviewed"),
                Field("date"),
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
