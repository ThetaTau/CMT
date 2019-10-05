from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton


class BallotListFormHelper(FormHelper):
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
                    '<i class="fas fa-search"></i> Filter Ballots',
                    Row(
                        InlineField('name__icontains'),
                        InlineField('type'),
                        InlineField('due_date'),
                        InlineField('voters'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )
                    )
                ),
    )


class BallotCompleteListFormHelper(FormHelper):
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
                    '<i class="fas fa-search"></i> Filter Complete Ballots',
                    Row(
                        InlineField('ballot__name__icontains'),
                        InlineField('ballot__due_date'),
                        InlineField('user__chapter__region'),
                        InlineField('motion'),
                        InlineField('ballot__type'),
                        InlineField('ballot__voters'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )
                    )
                ),
    )
