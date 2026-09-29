"""Тесты CloudPayments helpers из api.utils."""

from http import HTTPMethod, HTTPStatus
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import zapros

from api.utils import (
    check_cloudpayments_connection,
    check_donor_subscriptions,
    handling_cloudpayment_data,
)
from donor_base.constants import SubscriptionStatuses


@pytest.mark.django_db
def test_check_donor_subscriptions_builds_basic_auth_and_returns_active(
    settings,
    faker,
):
    """CloudPayments Model=true преобразуется в активную подписку."""
    email = faker.unique.email()
    settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = "https://cloud.test/find"
    settings.CLOUDPAYMENTS_PUBLIC_ID = "public"
    settings.CLOUDPAYMENTS_API_SECRET = "secret"
    response = Mock()
    response.json.return_value = {"Model": [{"Id": 1}]}

    with patch("api.utils.http_client.request", return_value=response) as request:  # noqa: E501
        result = check_donor_subscriptions(email)

    assert result == SubscriptionStatuses.ACTIVE.capitalized
    request.assert_called_once()
    method, url = request.call_args.args
    assert method == "POST"
    assert url == settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL
    assert request.call_args.kwargs["headers"] == {
        "Authorization": "Basic cHVibGljOnNlY3JldA=="
    }
    assert request.call_args.kwargs["json"] == {"accountId": email}


@pytest.mark.django_db
def test_check_donor_subscriptions_returns_inactive_for_empty_model(
    settings,
    faker,
):
    """CloudPayments Model=false преобразуется в неактивную подписку."""
    settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = "https://cloud.test/find"
    response = Mock()
    response.json.return_value = {"Model": None}

    with patch("api.utils.http_client.request", return_value=response):
        result = check_donor_subscriptions(faker.unique.email())

    assert result == SubscriptionStatuses.INACTIVE.capitalized


@pytest.mark.django_db
def test_handling_cloudpayment_data_maps_model_and_updates_donor(faker):
    """Данные CloudPayments мапятся в сериализатор и передаются в donor flow."""  # noqa: E501
    email = faker.unique.email()
    request = SimpleNamespace(data={
        "Model": [{
            "Email": email,
            "Amount": 100,
            "CreatedDateIso": "2024-01-02T03:04:05",
            "ConfirmDateIso": "2024-01-02T03:05:05",
            "TransactionId": 123,
            "Status": "Completed",
            "CardType": "Visa",
            "Currency": "RUB",
        }]
    })

    with (
        patch(
            "api.utils.check_donor_subscriptions",
            return_value=SubscriptionStatuses.ACTIVE.capitalized,
        ) as check_subscription,
        patch("api.utils.create_or_update_donor") as update_donor,
    ):
        result = handling_cloudpayment_data(request)

    assert result == {
        "email": email,
        "donat": 100,
        "date_created": "2024-01-02T03:04:05",
        "date_processed": "2024-01-02T03:05:05",
        "payment_id": 123,
        "status": "Completed",
        "payment_operator": "Cloudpayment",
        "payment_method": "Visa",
        "user_account_id": 123,
        "currency": "RUB",
    }
    check_subscription.assert_called_once_with(email)
    update_donor.assert_called_once_with(
        result,
        SubscriptionStatuses.ACTIVE.capitalized,
    )


@pytest.mark.parametrize("data", [{}, {"Model": []}, []])
def test_handling_cloudpayment_data_rejects_wrong_structure(data):
    """Неверная структура webhook CloudPayments приводит к ValueError."""
    request = SimpleNamespace(data=data)

    with pytest.raises((ValueError, IndexError)):
        handling_cloudpayment_data(request)


def test_check_cloudpayments_connection_returns_true_on_success(settings):
    """Успешная проверка ключей CloudPayments возвращает True."""
    settings.CLOUDPAYMENTS_API_TEST_URL = "https://cloud.test/ping"

    with patch("api.utils.http_client.request") as request:
        assert check_cloudpayments_connection() is True

    request.assert_called_once_with(
        HTTPMethod.POST,
        settings.CLOUDPAYMENTS_API_TEST_URL,
        headers={"Content-Type": "application/json"},
        auth=(
            settings.CLOUDPAYMENTS_PUBLIC_ID,
            settings.CLOUDPAYMENTS_API_SECRET,
        ),
    )


@pytest.mark.parametrize("status_code", [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])  # noqa: E501
def test_check_cloudpayments_connection_returns_false_for_bad_keys(status_code):  # noqa: E501
    """Ошибки авторизации CloudPayments означают невалидные ключи."""
    error = zapros.StatusCodeError(zapros.Response(status=status_code))

    with patch("api.utils.http_client.request", side_effect=error):
        assert check_cloudpayments_connection() is False


def test_check_cloudpayments_connection_reraises_unexpected_status():
    """Неожиданные статусы CloudPayments пробрасываются вызывающему коду."""
    error = zapros.StatusCodeError(
        zapros.Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)
    )

    with patch("api.utils.http_client.request", side_effect=error):
        with pytest.raises(zapros.StatusCodeError) as caught:
            check_cloudpayments_connection()

    assert caught.value is error
