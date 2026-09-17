from datetime import datetime
from json import JSONDecodeError
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import is_aware
from unittest.mock import PropertyMock

from api.utils import (
    ad_donor,
    check_donor_subscriptions,
    donor_exists,
    string_to_date
)
from contacts.models import Donor
from donor_base.test_settings import (
    GROUPS,
    IMPORT_UNISENDER,
    SUBSCRIPTION_CHOICES,
    UNISENDER_API_KEY,
)


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
def test_check_donor_subscription(
    mock_http_response,
    email,
    response,
    error,
    sub_status
):
    if error is JSONDecodeError:
        type(mock_http_response).json = PropertyMock(
            side_effect=JSONDecodeError('Expecting value', '', 0)
        )
    else:
        mock_http_response.json = response

    if error is not None:
        with pytest.raises(error):
            check_donor_subscriptions(email)
        return

    result = check_donor_subscriptions(email)
    assert result == sub_status


@pytest.mark.django_db
@pytest.mark.parametrize(
    'email, sub_status, update',
    [
        ('new_active@example.com', SUBSCRIPTION_CHOICES[0][0], False),
        ('new_inactive@example.com', SUBSCRIPTION_CHOICES[1][0], False),
        ('old_active@example.com', SUBSCRIPTION_CHOICES[0][0], True),
        (
            'old_active_pay_declined@example.com',
            SUBSCRIPTION_CHOICES[2][0],
            True
        )
    ]
)
def test_ad_donor(mock_http_client, email, sub_status, update):
    mock_client = mock_http_client

    if update:
        Donor.objects.create(
            email=email,
            subscription=SUBSCRIPTION_CHOICES[0][0],
            count_declined=1,
        )

    ad_donor(email, sub_status, update)

    assert Donor.objects.filter(email=email, subscription=sub_status).exists()

    donor_obj = Donor.objects.get(email=email)
    assert donor_obj.count_declined == 0

    mock_client.post_form.assert_called_once_with(
        IMPORT_UNISENDER,
        {
            'format': 'json',
            'api_key': UNISENDER_API_KEY,
            'overwrite_lists': 1 if update else 0,
            'field_names[0]': 'email',
            'field_names[1]': 'email_list_ids',
            'data[0][0]': email,
            'data[0][1]': GROUPS[sub_status],
        }
    )
