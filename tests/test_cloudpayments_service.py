"""Тесты выполняемых на текущем коде сценариев CloudPayments."""

from base64 import b64decode
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPMethod, HTTPStatus
from typing import Any

import pytest
import zapros
from faker import Faker
from inline_snapshot import snapshot
from pytest_django.fixtures import Settings
from rest_framework.request import Request
from zapros.mock import Mock

from api.cloudpayments_service import (
    check_cloudpayments_connection,
    check_donor_subscriptions,
    handling_cloudpayment_data,
)
from api.serializers import CloudpaymentsSerializer
from cloudpayments.models import CloudPayment
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses

CLOUDPAYMENTS_TEST_URL = "https://cloudpayments.test/test"
CLOUDPAYMENTS_FIND_URL = (
    "https://api.cloudpayments.example/subscriptions/find"
)
TEST_PUBLIC_ID = "test-public-id"
TEST_CREDENTIAL = "test-api-secret"
TEST_EMAIL = "donor@example.org"


@pytest.fixture
def cloudpayments_settings(settings: Settings) -> None:
    """Настраивает общие тестовые значения CloudPayments."""
    settings.CLOUDPAYMENTS_API_TEST_URL = CLOUDPAYMENTS_TEST_URL
    settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = CLOUDPAYMENTS_FIND_URL
    settings.CLOUDPAYMENTS_PUBLIC_ID = TEST_PUBLIC_ID
    settings.CLOUDPAYMENTS_API_SECRET = TEST_CREDENTIAL


@pytest.mark.usefixtures("zapros_router")
def test_connection_returns_false_without_test_url(
    settings: Settings,
    cloudpayments_settings: None,
) -> None:
    """Отсутствующий URL не приводит к HTTP-запросу."""
    settings.CLOUDPAYMENTS_API_TEST_URL = None

    assert check_cloudpayments_connection() is False


def test_connection_returns_true_and_sends_auth(
    cloudpayments_settings: None,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Успешная проверка credentials использует Basic Auth."""
    route = route_zapros_response(
        HTTPMethod.POST,
        CLOUDPAYMENTS_TEST_URL,
        zapros.Response(
            status=HTTPStatus.OK,
            json={},
        ),
    )

    assert check_cloudpayments_connection() is True

    request = route.calls[0]
    assert request.method == HTTPMethod.POST
    assert request.headers["Content-Type"] == "application/json"

    scheme, encoded_credentials = request.headers["Authorization"].split(
        maxsplit=1,
    )
    assert scheme == "Basic"
    assert b64decode(encoded_credentials, validate=True) == (
        f"{TEST_PUBLIC_ID}:{TEST_CREDENTIAL}".encode()
    )


@pytest.mark.parametrize(
    "status_code",
    [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN],
)
def test_connection_returns_false_for_bad_credentials(
    cloudpayments_settings: None,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    *,
    status_code: HTTPStatus,
) -> None:
    """401 и 403 от CloudPayments означают отклонённые credentials."""
    route_zapros_response(
        HTTPMethod.POST,
        CLOUDPAYMENTS_TEST_URL,
        zapros.Response(status=status_code),
    )

    assert check_cloudpayments_connection() is False


def test_connection_reraises_unexpected_status(
    cloudpayments_settings: None,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Неожиданный status остаётся zapros.StatusCodeError."""
    route_zapros_response(
        HTTPMethod.POST,
        CLOUDPAYMENTS_TEST_URL,
        zapros.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR),
    )

    with pytest.raises(zapros.StatusCodeError):
        check_cloudpayments_connection()


@pytest.mark.parametrize(
    ("payload", "error_type"),
    [
        ({}, ValueError),
        ([], ValueError),
        ({"Model": []}, IndexError),
    ],
)
def test_handling_rejects_invalid_structure(
    drf_json_request: Callable[[Any], Request],
    *,
    payload: Any,
    error_type: type[Exception],
) -> None:
    """Структура без данных Model или с пустым Model отклоняется."""
    with pytest.raises(error_type):
        handling_cloudpayment_data(drf_json_request(payload))


@pytest.mark.django_db
@pytest.mark.usefixtures("sync_task", "email_task", "chain_factory")
def test_handling_maps_payment_and_updates_donor(
    cloudpayment_payload: dict[str, Any],
    drf_json_request: Callable[[Any], Request],
    cloudpayments_settings: None,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Mapping webhook использует реальный lookup и обновляет Donor."""
    subscription_route = route_zapros_response(
        HTTPMethod.POST,
        CLOUDPAYMENTS_FIND_URL,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"Model": [{"Id": "subscription-id"}]},
        ),
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = handling_cloudpayment_data(
            drf_json_request(cloudpayment_payload),
        )

    model = cloudpayment_payload["Model"][0]
    assert result == snapshot(
        {
            "email": model["Email"],
            "donat": model["Amount"],
            "date_created": model["CreatedDateIso"],
            "date_processed": model["ConfirmDateIso"],
            "payment_id": model["TransactionId"],
            "status": model["Status"],
            "payment_operator": "Cloudpayment",
            "payment_method": model["CardType"],
            "user_account_id": model["TransactionId"],
            "currency": model["Currency"],
        },
    )
    assert Donor.objects.get(email=model["Email"]).subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )
    subscription_route.assert_called_once()


@pytest.fixture
def serializer_data(faker: Faker) -> dict[str, Any]:
    """Возвращает общие поля для CloudpaymentsSerializer."""
    return {
        "email": faker.unique.email(),
        "donat": 100,
        "custom_donat": 0,
        "payment_method": "Visa",
        "monthly_donat": False,
        "subscription": False,
        "status": "Completed",
        "currency": "RUB",
        "user_account_id": 12345,
        "date_created": datetime(
            2024,
            1,
            2,
            3,
            4,
            5,
            tzinfo=UTC,
        ),
        "date_processed": datetime(
            2024,
            1,
            2,
            3,
            5,
            5,
            tzinfo=UTC,
        ),
    }


@pytest.mark.django_db
def test_cloudpayment_serializer_saves_valid_data(
    serializer_data: dict[str, Any],
) -> None:
    """Serializer сохраняет валидный платёж в тестовую БД."""
    serializer = CloudpaymentsSerializer(data=serializer_data)

    assert serializer.is_valid(), serializer.errors
    payment = serializer.save()

    assert isinstance(payment, CloudPayment)
    assert payment.donat == 100
    assert payment.payment_method == "Visa"
    assert payment.status == "Completed"


@pytest.mark.django_db
def test_cloudpayment_serializer_rejects_negative_amount(
    serializer_data: dict[str, Any],
) -> None:
    """Serializer отклоняет отрицательную сумму платежа."""
    serializer = CloudpaymentsSerializer(
        data=serializer_data | {"donat": -1},
    )

    assert not serializer.is_valid()
    assert "donat" in serializer.errors


@pytest.mark.parametrize(
    ("model", "expected_subscription"),
    [
        (
            [{"Id": "subscription-id"}],
            SubscriptionStatuses.ACTIVE.capitalized,
        ),
        (
            [],
            SubscriptionStatuses.INACTIVE.capitalized,
        ),
    ],
    ids=["active", "inactive"],
)
def test_check_donor_subscriptions_maps_model_presence(
    cloudpayments_settings: None,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    *,
    model: list[dict[str, str]],
    expected_subscription: str,
) -> None:
    """Непустая Model активирует подписку, пустая — деактивирует."""
    route = route_zapros_response(
        HTTPMethod.POST,
        CLOUDPAYMENTS_FIND_URL,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"Model": model},
        ),
    )

    result = check_donor_subscriptions(TEST_EMAIL)

    route.assert_called_once()
    assert result == expected_subscription
