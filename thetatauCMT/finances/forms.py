from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, StrictButton, Field


class TransactionListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'transaction-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Transactions',
                    Row(
                        Field('type'),
                        Field('paid'),
                        Field('estimate'),
                        Field('due_date'),
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


class ChapterBalanceListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'balance-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Balances',
                    Row(
                        Field('region'),
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
