import django_tables2 as tables
from .models import Guard, Badge, Initiation, Depledge, StatusChange,\
    PledgeForm, Audit


class GuardTable(tables.Table):
    class Meta:
        model = Guard
        fields = ('name', 'cost', 'description',
                  'letters',
                  )
        attrs = {"class": "table-striped table-bordered"}


class BadgeTable(tables.Table):
    class Meta:
        model = Badge
        fields = ('name', 'cost', 'description',
                  )
        attrs = {"class": "table-striped table-bordered"}


class PledgeFormTable(tables.Table):
    created = tables.DateColumn(verbose_name="Submitted")

    class Meta:
        model = PledgeForm
        fields = ('name', 'created')
        attrs = {"class": "table-striped table-bordered"}


class InitiationTable(tables.Table):
    user = tables.Column(accessor='user.name')
    date = tables.DateColumn(verbose_name="Initiation Date")
    created = tables.DateColumn(verbose_name="Submitted")

    class Meta:
        model = Initiation
        fields = ('user', 'date', 'created')
        attrs = {"class": "table-striped table-bordered"}


class DepledgeTable(tables.Table):
    user = tables.Column(accessor='user.name')
    date = tables.DateColumn(verbose_name="Depledge Date")
    created = tables.DateColumn(verbose_name="Submitted")

    class Meta:
        model = Depledge
        fields = ('user', 'date', 'created')
        attrs = {"class": "table-striped table-bordered"}


class StatusChangeTable(tables.Table):
    user = tables.Column(accessor='user.name')
    date_start = tables.DateColumn(verbose_name="Change Date")
    created = tables.DateColumn(verbose_name="Form Submitted")

    class Meta:
        model = StatusChange
        fields = ('user', 'date_start', 'created', 'reason', 'date_end')
        attrs = {"class": "table-striped table-bordered"}


class AuditTable(tables.Table):
    debit_card_access = tables.Column("Debit Card Access")

    class Meta:
        model = Audit
        attrs = {"class": "table-striped table-bordered"}
        fields = [
            'user.chapter',
            'user.chapter.region',
            'modified',
            'dues_member',
            'dues_pledge',
            'frequency',
            'balance_checking',
            'balance_savings',
            'debit_card',
            'debit_card_access',
            'payment_plan',
            'cash_book',
            'cash_book_reviewed',
            'cash_register',
            'cash_register_reviewed',
            'member_account',
            'member_account_reviewed',
        ]
