"""Тесты выполняемых на текущем коде сценариев CloudPayments."""

from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPMethod, HTTPStatus
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import dishka
import pytest
import zapros
from django.test import override_settings
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter

from api import cloudpayments_service
from api.cloudpayments_service import (
    check_cloudpayments_connection,
    check_donor_subscriptions,
    handling_cloudpayment_data,
)
from api.serializers import CloudpaymentsSerializer
from cloudpayments.models import CloudPayment
from contacts.models import Donor
from donor_base import di
from donor_base.constants import SubscriptionStatuses


def test_connection_returns_false_without_test_url(
    settings: Any,
    zapros_router: MockRouter,
) -> None:
    """Отсутствующий URL не приводит к HTTP-запросу."""
    settings.CLOUDPAYMENTS_API_TEST_URL = None

    assert check_cloudpayments_connection() is False


def test_connection_returns_true_and_sends_auth(
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Успешная проверка credentials использует Basic Auth."""
    url = "https://cloudpayments.test/test"
    settings.CLOUDPAYMENTS_API_TEST_URL = url
    settings.CLOUDPAYMENTS_PUBLIC_ID = "public"
    test_value = "secret"
    settings.CLOUDPAYMENTS_API_SECRET = test_value
    route = route_zapros_response(
        HTTPMethod.POST,
        url,
        zapros.Response(
            status=HTTPStatus.OK,
            json={},
        ),
    )

    assert check_cloudpayments_connection() is True

    request = route.calls[0]
    assert request.method == HTTPMethod.POST
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Authorization"] == "Basic cHVibGljOnNlY3JldA=="


@pytest.mark.parametrize(
    "status_code",
    [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN],
)
def test_connection_returns_false_for_bad_credentials(
    status_code: HTTPStatus,
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """401 и 403 от CloudPayments означают отклонённые credentials."""
    url = "https://cloudpayments.test/test"
    settings.CLOUDPAYMENTS_API_TEST_URL = url
    route_zapros_response(
        HTTPMethod.POST,
        url,
        zapros.Response(status=status_code),
    )

    assert check_cloudpayments_connection() is False


def test_connection_reraises_unexpected_status(
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Неожиданный status остаётся zapros.StatusCodeError."""
    url = "https://cloudpayments.test/test"
    settings.CLOUDPAYMENTS_API_TEST_URL = url
    route_zapros_response(
        HTTPMethod.POST,
        url,
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
    payload: Any,
    error_type: type[Exception],
    drf_json_request: Callable[[Any], Any],
) -> None:
    """Структура без данных Model или с пустым Model отклоняется."""
    with pytest.raises(error_type):
        handling_cloudpayment_data(drf_json_request(payload))


@pytest.mark.django_db
def test_handling_maps_payment_and_updates_donor(
    cloudpayment_payload: dict[str, Any],
    drf_json_request: Callable[[Any], Any],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
    django_capture_on_commit_callbacks: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяется mapping webhook и реальное изменение записи Donor."""
    def active_subscription(_email: str) -> str:
        return SubscriptionStatuses.ACTIVE.capitalized

    monkeypatch.setattr(
        cloudpayments_service,
        "check_donor_subscriptions",
        active_subscription,
    )

    with django_capture_on_commit_callbacks(execute=True):
        result = handling_cloudpayment_data(
            drf_json_request(cloudpayment_payload),
        )

    model = cloudpayment_payload["Model"][0]
    assert result == {
        "email": model["Email"],
        "donat": 100,
        "date_created": "2024-01-02T03:04:05Z",
        "date_processed": "2024-01-02T03:05:05Z",
        "payment_id": 12345,
        "status": "Completed",
        "payment_operator": "Cloudpayment",
        "payment_method": "Visa",
        "user_account_id": 12345,
        "currency": "RUB",
    }
    assert Donor.objects.get(email=model["Email"]).subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )


def _serializer_data(email: str, amount: int) -> dict[str, Any]:
    """Строит поля, необходимые CloudpaymentsSerializer."""
    return {
        "email": email,
        "donat": amount,
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
    faker: Any,
) -> None:
    """Serializer сохраняет валидный платёж в тестовую БД."""
    serializer = CloudpaymentsSerializer(
        data=_serializer_data(faker.unique.email(), 100),
    )

    assert serializer.is_valid(), serializer.errors
    payment = serializer.save()

    assert isinstance(payment, CloudPayment)
    assert payment.donat == 100
    assert payment.payment_method == "Visa"
    assert payment.status == "Completed"


@pytest.mark.django_db
def test_cloudpayment_serializer_rejects_negative_amount(
    faker: Any,
) -> None:
    """Serializer отклоняет отрицательную сумму платежа."""
    serializer = CloudpaymentsSerializer(
        data=_serializer_data(faker.unique.email(), -1),
    )

    assert not serializer.is_valid()
    assert "donat" in serializer.errors


def test_check_donor_subscriptions_returns_active_for_nonempty_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Непустая Model в ответе CloudPayments означает активную подписку."""
    url = "https://api.cloudpayments.example/subscriptions/find"
    parsed_url = urlsplit(url)
    assert parsed_url.hostname is not None

    router = MockRouter()
    response_mock = Mock.given(
        path(parsed_url.path)
        .method(HTTPMethod.POST)
        .host(parsed_url.hostname),
    ).respond(
        zapros.Response(
            status=HTTPStatus.OK,
            json={"Model": [{"Id": "subscription-id"}]},
        ),
    )
    router.add(response_mock)

    client = zapros.Client(handler=MockMiddleware(router))
    container = dishka.make_container(context={zapros.Client: client})
    monkeypatch.setattr(di, "container", container)

    test_value = "test-api-secret"

    try:
        with override_settings(
            CLOUDPAYMENTS_PUBLIC_ID="test-public-id",
            CLOUDPAYMENTS_API_SECRET=test_value,
            CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL=url,
        ):
            status = check_donor_subscriptions("donor@example.org")
    finally:
        container.close()

    response_mock.assert_called_once()
    assert status == SubscriptionStatuses.ACTIVE.capitalized
