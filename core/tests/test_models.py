from faker import Faker
import pytest
from django.core.exceptions import ValidationError
from core import models


fake = Faker()


def test_no_future():
    date = fake.date_between(start_date="-4y")
    models.no_future(date)


def test_no_future_false():
    date = fake.date_between(start_date="+1d", end_date="+4y")
    with pytest.raises(ValidationError):
        models.no_future(date)
