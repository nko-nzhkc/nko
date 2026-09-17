from datetime import datetime
from json import JSONDecodeError
from typing import TypedDict, TypeAlias
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import is_aware
from unittest.mock import MagicMock, Mock, PropertyMock


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


class InnerItem(TypedDict):
    """Единичная пара ключ-значение внутри списка Model ответа Unisender."""
    item_key: str
    item_value: str


# Структура декодированного JSON-тела мокированного HTTP-ответа Unisender.
Response: TypeAlias = dict[str, list[InnerItem] | bool | None]


@pytest.mark.parametrize(
    'date_string, expected',
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
def test_string_to_date(
    date_string: str | None,
    expected: datetime | type[ValueError] | type[TypeError],
) -> None:
    """Проверяет преобразование строки в datetime и наличие временной зоны.

    Если *expected* является классом исключения, функция должна его выбросить.
    В противном случае результат должен совпадать с *expected* и быть
    timezone-aware.
    """
    if expected in (TypeError, ValueError):
        with pytest.raises((TypeError, ValueError)):
            string_to_date(date_string)
    else:
        convertion_result = string_to_date(date_string)
        assert convertion_result == expected
        assert is_aware(convertion_result)


@pytest.mark.django_db
def test_donor_exists_donor_in_db() -> None:
    """Проверяет корретный кейс работы donor_exists.

    donor_exists возвращает True, если email присутствует в базе данных.
    """
    Donor.objects.create(email='donor@example.com')
    assert donor_exists(email='donor@example.com') is True


@pytest.mark.django_db
def test_donor_exists_donor_not_in_db() -> None:
    """Проверяет ошибочный кейс работы donor_exists.

    donor_exists возвращает False, если email отсутствует в базе данных.
    """
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
    mock_http_response: Mock,
    email: str,
    response: Response | None,
    error: type[KeyError] | type[JSONDecodeError] | None,
    sub_status: str | None,
) -> None:
    """Проверяет check_donor_subscriptions на различных формах HTTP-ответа.

    Args:
        mock_http_response: Фикстура с мокированным объектом HTTP-ответа.
        email: Email донора, передаваемый в тестируемую функцию.
        response: Декодированное JSON-тело, которое должен вернуть мок,
            или None для имитации повреждённого JSON.
        error: Ожидаемый класс исключения или None, если исключение
            не ожидается.
        sub_status: Ожидаемый статус подписки, возвращаемый при успехе.
    """
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

    check_result = check_donor_subscriptions(email)
    assert check_result == sub_status


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
def test_ad_donor(
    mock_http_client: MagicMock,
    email: str,
    sub_status: str,
    update: bool,
) -> None:
    """Проверяет, создание/обновление донора и вызов API Unisender в ad_donor.

    В случаях с *update* предварительно создаётся донор с другим статусом
    подписки (для случая деактивации) и ненулевым счётчиком отклонений,
    чтобы убедиться, что оба поля корректно перезаписываются.

    Args:
        mock_http_client: Фикстура с мокированным HTTP-клиентом, внедряемым
            в тестируемую функцию.
        email: Email донора для создания или поиска.
        sub_status: Целевой статус подписки, который должен быть применён.
        update: Если True, донор создаётся заранее для проверки ветки
            обновления.
    """
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
