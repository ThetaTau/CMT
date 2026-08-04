"""Shared django-tables2 base class.

django-tables2 fills an empty cell with an em dash. The CMT does not use em
dashes anywhere a member can read them, so the placeholder is overridden once
here rather than in each table's ``Meta`` (``Meta`` options are rebuilt per
class by the metaclass, so they do not inherit reliably).
"""

import django_tables2 as tables

EMPTY_VALUE = "None"


class CMTTable(tables.Table):
    """A ``django_tables2.Table`` that writes "None" into empty cells."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", EMPTY_VALUE)
        super().__init__(*args, **kwargs)
