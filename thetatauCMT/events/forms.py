from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton


class EventListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'event-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Events',
                    Row(
                        InlineField('name'),
                        InlineField('date'),
                        InlineField('type'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Search',
                                type='submit',
                                css_class='btn-primary',
                                style='margin-top:10px;')
                        )
                    )
                ),
    )
