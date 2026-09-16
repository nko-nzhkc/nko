import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils.timezone import is_aware

from api.utils import string_to_date, donor_exists
from contacts.models import Donor


@pytest.mark.parametrize(
    'value, expected',
    [
        (
            '2026-9-16 17:00:00',
            datetime(2026, 9, 16, 17, 0, 0, tzinfo=ZoneInfo(key='UTC'))
        ),
        ('Неверная строка', ValueError),
        ('', ValueError),
        (None, TypeError),
    ]
)
def test_string_to_date(value: str, expected: datetime):
    if expected in (TypeError, ValueError):
        with pytest.raises((TypeError, ValueError)):
            string_to_date(value)
    else:
        result = string_to_date(value)
        assert result == expected
        assert is_aware(result)


@pytest.mark.django_db
def test_donor_exists_donor_in_db():
    Donor.objects.create(email='donor@example.com')
    assert donor_exists(email='donor@example.com') is True


@pytest.mark.django_db
def test_donor_exists_donor_not_in_db():
    assert donor_exists(email='nonexistent@example.com') is False
