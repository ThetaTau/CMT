import datetime
import importlib
from faker import Faker
import pytest
from django.core.exceptions import ValidationError
from core import models

fake = Faker()


@pytest.mark.freeze_time("2018-03-15")
def test_today():
    importlib.reload(models)
    assert models.TODAY == datetime.date(2018, 3, 15)


@pytest.mark.freeze_time("2018-03-15")
def test_core_dates_even_spring():
    importlib.reload(models)
    # Convention was in 2018, so biennium started 2016
    assert models.BIENNIUM_START == 2016
    assert models.BIENNIUM_START_DATE == datetime.date(2016, 7, 1)
    assert models.BIENNIUM_DATES == {
        "Fall 2016": {
            "start": datetime.datetime(2016, 7, 1),
            "end": datetime.datetime(2016, 12, 31),
        },
        "Spring 2017": {
            "start": datetime.datetime(2017, 1, 1),
            "end": datetime.datetime(2017, 6, 30),
        },
        "Fall 2017": {
            "start": datetime.datetime(2017, 7, 1),
            "end": datetime.datetime(2017, 12, 31),
        },
        "Spring 2018": {
            "start": datetime.datetime(2018, 1, 1),
            "end": datetime.datetime(2018, 6, 30),
        },
    }
    assert models.BIENNIUM_YEARS == [2016, 2017, 2017, 2018]
    assert models.current_term() == "sp"
    assert models.current_year() == 2018
    assert models.current_year_term_slug() == f"Spring_2018"


@pytest.mark.freeze_time("2019-10-21")
def test_core_dates_odd_fall():
    importlib.reload(models)
    assert models.BIENNIUM_START == 2018
    assert models.BIENNIUM_START_DATE == datetime.date(2018, 7, 1)
    assert models.BIENNIUM_DATES == {
        "Fall 2018": {
            "start": datetime.datetime(2018, 7, 1),
            "end": datetime.datetime(2018, 12, 31),
        },
        "Spring 2019": {
            "start": datetime.datetime(2019, 1, 1),
            "end": datetime.datetime(2019, 6, 30),
        },
        "Fall 2019": {
            "start": datetime.datetime(2019, 7, 1),
            "end": datetime.datetime(2019, 12, 31),
        },
        "Spring 2020": {
            "start": datetime.datetime(2020, 1, 1),
            "end": datetime.datetime(2020, 6, 30),
        },
    }
    assert models.BIENNIUM_YEARS == [2018, 2019, 2019, 2020]
    assert models.current_term() == "fa"
    assert models.current_year() == 2019
    assert models.current_year_term_slug() == f"Fall_2019"


def test_forever():
    assert models.forever() == datetime.datetime(4755, 11, 29, 0, 0)


def test_no_future():
    date = fake.date_between(start_date="-4y")
    models.no_future(date)


def test_no_future_false():
    date = fake.date_between(start_date="+1d", end_date="+4y")
    with pytest.raises(ValidationError):
        models.no_future(date)


@pytest.mark.freeze_time("2020-05-21")
@pytest.mark.parametrize(
    "given_date,expected_dates",
    [
        (
            datetime.date(2016, 10, 1),
            (datetime.datetime(2016, 7, 1), datetime.datetime(2017, 1, 1),),
        ),
        (
            datetime.date(2018, 3, 1),
            (datetime.datetime(2018, 1, 1), datetime.datetime(2018, 7, 1),),
        ),
        (None, (datetime.datetime(2020, 1, 1), datetime.datetime(2020, 7, 1),),),
    ],
)
def test_semester_encompass_start_end_date(given_date, expected_dates):
    assert models.semester_encompass_start_end_date(given_date) == expected_dates


@pytest.mark.freeze_time("2020-05-21")
@pytest.mark.parametrize(
    "given_date,expected_dates",
    [
        (
            datetime.date(2016, 10, 1),
            (datetime.datetime(2016, 7, 1), datetime.datetime(2017, 7, 1),),
        ),
        (
            datetime.date(2018, 3, 1),
            (datetime.datetime(2017, 7, 1), datetime.datetime(2018, 7, 1),),
        ),
        ("2019", (datetime.datetime(2019, 7, 1), datetime.datetime(2020, 7, 1),),),
        (None, (datetime.datetime(2019, 7, 1), datetime.datetime(2020, 7, 1),),),
    ],
)
def test_academic_encompass_start_end_date(given_date, expected_dates):
    assert models.academic_encompass_start_end_date(given_date) == expected_dates
