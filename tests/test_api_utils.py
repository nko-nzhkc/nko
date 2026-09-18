from datetime import datetime
from json import JSONDecodeError
from types import MappingProxyType
from typing import Callable, TypedDict, TypeAlias
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import is_aware
from unittest.mock import MagicMock, Mock, PropertyMock, call

from donor_base import test_settings as settings
from api.utils import (
    ad_donor,
    check_donor_subscriptions,
    donor_exists,
    send_payment_email,
    string_to_date,
)
from contacts.models import Donor


EXAMPLE_EMAIL = "donor@example.com"
BASE_PAYLOAD = MappingProxyType({
    "format": "json",
    "api_key": settings.UNISENDER_API_KEY,
})
EXAMPLE_DATE = (2026, 9, 16, 17, 0, 0)


class InnerItem(TypedDict):
    """Единичная пара ключ-значение внутри списка Model ответа Unisender."""
    item_key: str
    item_value: str


# Структура декодированного JSON-тела мокированного HTTP-ответа Unisender.
Response: TypeAlias = dict[str, list[InnerItem] | bool | None]


@pytest.mark.parametrize(
    "date_string, expected",
    [
        (
            "2026-9-16 17:00:00",
            datetime(*EXAMPLE_DATE, tzinfo=ZoneInfo(key="UTC"))
        ),
        ("Неверная строка", ValueError),
        ("", ValueError),
        (None, TypeError),
    ],
    ids=[
        "valid_date_string",
        "invalid_date_string",
        "empty_string",
        "none_input",
    ],
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
    Donor.objects.create(email=EXAMPLE_EMAIL)
    assert donor_exists(email=EXAMPLE_EMAIL) is True


@pytest.mark.django_db
def test_donor_exists_donor_not_in_db() -> None:
    """Проверяет ошибочный кейс работы donor_exists.

    donor_exists возвращает False, если email отсутствует в базе данных.
    """
    assert donor_exists(email="nonexistent@example.com") is False


@pytest.mark.parametrize(
    "email, response, error, sub_status",
    [
        (
            "sub_email@example.com",
            {
                "Model": [{"value": "non_empty"}],
                "Success": True,
                "Message": None
            },
            None,
            settings.SUBSCRIPTION_CHOICES[0][0]
        ),
        (
            "no_sub_email@example.com",
            {
                "Model": [],
                "Success": True,
                "Message": None
            },
            None,
            settings.SUBSCRIPTION_CHOICES[1][0]
        ),
        (
            "wrong_response@example.com",
            {
                "Success": False,
                "Message": None
            },
            KeyError,
            None
        ),
        (
            "broken_json@example.com",
            None,
            JSONDecodeError,
            None
        ),
    ],
    ids=[
        "subscribed",
        "not_subscribed",
        "missing_model_key",
        "broken_json",
    ],
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
            side_effect=JSONDecodeError("Expecting value", "", 0)
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
    "email, sub_status, update",
    [
        (
            "new_active@example.com",
            settings.SUBSCRIPTION_CHOICES[0][0],
            False,
        ),
        (
            "new_inactive@example.com",
            settings.SUBSCRIPTION_CHOICES[1][0],
            False,
        ),
        (
            "old_active@example.com",
            settings.SUBSCRIPTION_CHOICES[0][0],
            True,
        ),
        (
            "old_active_pay_declined@example.com",
            settings.SUBSCRIPTION_CHOICES[2][0],
            True
        )
    ],
    ids=[
        "create_active_subscriber",
        "create_inactive_subscriber",
        "update_active_subscriber",
        "update_payment_declined_subscriber",
    ],
)
def test_ad_donor(
    mock_http_client: MagicMock,
    email: str,
    sub_status: str,
    update: bool,
) -> None:
    """Проверяет создание/обновление донора и вызов API Unisender в ad_donor.

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
            subscription=settings.SUBSCRIPTION_CHOICES[0][0],
            count_declined=1,
        )

    ad_donor(email, sub_status, update)

    assert Donor.objects.filter(email=email, subscription=sub_status).exists()

    donor_obj = Donor.objects.get(email=email)
    assert donor_obj.count_declined == 0

    mock_client.post_form.assert_called_once_with(
        settings.IMPORT_UNISENDER,
        {
            **BASE_PAYLOAD,
            "overwrite_lists": 1 if update else 0,
            "field_names[0]": "email",
            "field_names[1]": "email_list_ids",
            "data[0][0]": email,
            "data[0][1]": settings.GROUPS[sub_status],
        }
    )


def test_send_payment_email_success(
    mock_http_client: MagicMock,
    mock_unisender_success: dict[str, str],
) -> None:
    email = EXAMPLE_EMAIL
    list_id = settings.GROUPS[settings.SUBSCRIPTION_CHOICES[0][0]]
    template = mock_unisender_success()

    send_payment_email(email, list_id)

    assert mock_http_client.post_form.call_count == 2

    first_call, second_call = mock_http_client.post_form.call_args_list

    assert first_call == call(
        settings.URL_GET_TEMP,
        {
            **BASE_PAYLOAD,
            "template_id": settings.TEMPLATE_ID,
        }
    )
    assert second_call == call(
        settings.URL_SEND_EMAIL,
        {
            **BASE_PAYLOAD,
            "email": email,
            "sender_email": settings.DEFAULT_FROM_EMAIL,
            "sender_name": settings.UNISENDER_SENDER_NAME,
            "subject": template["subject"],
            "body": template["body"],
            "list_id": list_id,
        }
    )


@pytest.mark.parametrize(
    "first_response",
    [
        {"error": "Invalid api_key", "code": "invalid_api_key"},
        {"unexpected_key": "unexpected_value"},
    ],
    ids=["error_in_response", "no_result_no_error"],
)
def test_send_payment_email_bad_template_response(
    mock_http_client: MagicMock,
    mock_unisender_error: Callable[[dict[str, str]], None],
    first_response: dict[str, str],
) -> None:
    """Проверяет отсутствие второго запроса при ошибке получения шаблона.

    Если ответ на запрос шаблона содержит ``"error"`` или не содержит
    ни ``"result"``, ни ``"error"``, функция должна прервать выполнение,
    не совершая второй вызов post_form.

    Args:
        mock_http_client: Фикстура с мокированным HTTP-клиентом.
        mock_unisender_error: Фикстура, настраивающая мок на ответ с ошибкой.
        first_response: Ответ на запрос шаблона, не содержащий ``"result"``.
    """
    mock_unisender_error(first_response)

    send_payment_email(EXAMPLE_EMAIL, "1")

    assert mock_http_client.post_form.call_count == 1
    mock_http_client.post_form.assert_called_once_with(
        settings.URL_GET_TEMP,
        {
            "format": "json",
            "api_key": settings.UNISENDER_API_KEY,
            "template_id": settings.TEMPLATE_ID,
        }
    )


def test_send_payment_email_bad_send_response(
    mock_http_client: MagicMock,
    mock_unisender_mixed: Callable[..., dict[str, str]],
) -> None:
    """Проверяет поведение при ошибке в ответе на отправку письма.

    Первый запрос (получение шаблона) завершается успешно, второй
    (отправка письма) возвращает ответ с ``"error"``. Функция должна
    совершить оба вызова post_form и не выбрасывать исключений.

    Args:
        mock_http_client: Фикстура с мокированным HTTP-клиентом.
        mock_unisender_mixed: Фикстура, задающая последовательность
            успешного ответа с шаблоном и ответа с ошибкой отправки.
    """
    email = EXAMPLE_EMAIL
    list_id = settings.GROUPS[settings.SUBSCRIPTION_CHOICES[0][0]]

    mock_unisender_mixed()

    send_payment_email(email, list_id)

    assert mock_http_client.post_form.call_count == 2
