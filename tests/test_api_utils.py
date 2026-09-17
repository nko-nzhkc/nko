from datetime import datetime
from json import JSONDecodeError
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import is_aware
from unittest.mock import PropertyMock

from api.utils import string_to_date, donor_exists, check_donor_subscriptions
from contacts.models import Donor
from donor_base.test_settings import SUBSCRIPTION_CHOICES


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


@pytest.mark.parametrize(
    'email, response, error, sub_status',
    [
        (
            'sub_email@example.com',
            {
                'Model': [{'value': 'non_empty'}],
                'Success': True,
                'Message': None
            },
            None,
            SUBSCRIPTION_CHOICES[0][0]
        ),
        (
            'no_sub_email@example.com',
            {
                'Model': [],
                'Success': True,
                'Message': None
            },
            None,
            SUBSCRIPTION_CHOICES[1][0]
        ),
        (
            'wrong_response@example.com',
            {
                'Success': False,
                'Message': None
            },
            KeyError,
            None
        ),
        (
            'broken_json@example.com',
            None,
            JSONDecodeError,
            None
        ),
    ]
)
def test_check_donor_subscription(mocker, email, response, error, sub_status):
    mock_http_client = mocker.patch('api.utils.http_client')
    mock_http_response = mocker.Mock()

    if error is JSONDecodeError:
        type(mock_http_response).json = PropertyMock(
            side_effect=JSONDecodeError('Expecting value', '', 0)
        )
    else:
        mock_http_response.json = response

    mock_http_client.request.return_value = mock_http_response

    if error is not None:
        with pytest.raises(error):
            check_donor_subscriptions(email)
        return

    result = check_donor_subscriptions(email)
    assert result == sub_status
