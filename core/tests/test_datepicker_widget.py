"""Regression tests for the shared ``core.forms.DatePicker`` widget.

The tempus-dominus picker gets its starting value from a JS ``moment`` option,
not from the input's ``value`` attribute, so the string handed to moment decides
what day the user sees. Two historical off-by-one-day bugs are locked in here:

* A bare ISO date (``"1995-03-27"``) is parsed by moment.js 2.x as UTC midnight,
  which renders as the previous day in any timezone behind UTC.
* A ``DateField`` whose initial is a ``datetime`` (a ``timezone.now`` model
  default, as on ``Event.date``) produces a tz-aware ISO instant that moment
  re-renders in the *browser's* timezone, again landing on a different day.
"""

import datetime

from django.utils import timezone

from core.forms import DatePicker


def test_bare_date_gets_midday_time():
    assert DatePicker().moment_option(datetime.date(1995, 3, 27)) == {"date": "1995-03-27T12:00:00"}


def test_aware_datetime_collapses_to_site_local_date():
    """``timezone.now`` defaults must not leak a UTC instant to moment.js."""
    # 05:30 UTC is still the previous day in the site timezone (America/Phoenix).
    value = datetime.datetime(2026, 8, 6, 5, 30, tzinfo=datetime.timezone.utc)
    assert DatePicker().moment_option(value) == {"date": timezone.localdate(value).isoformat() + "T12:00:00"}


def test_naive_datetime_keeps_its_own_date():
    value = datetime.datetime(2026, 8, 6, 5, 30)
    assert DatePicker().moment_option(value) == {"date": "2026-08-06T12:00:00"}


def test_id_for_label_matches_rendered_input_id():
    """tempus_dominus rewrites ``-`` to ``_`` in the id it renders, so a
    prefixed form's crispy ``<label for>`` has to follow."""
    assert DatePicker().id_for_label("id_user-birth_date") == "id_user_birth_date"
