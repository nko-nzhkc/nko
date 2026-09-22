"""Модуль бизнес логики CloudPayments."""

import base64
import logging
from http import HTTPMethod, HTTPStatus

import zapros
from django.conf import settings
from donor_base import http_client
from donor_base.constants import SubscriptionStatuses

from api.donor_service import create_or_update_donor

logger = logging.getLogger(__name__)

_CLOUDPAYMENTS_BAD_KEYS_STATUSES = frozenset(
    (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN),
)


def check_donor_subscriptions(email):
    """Проверка наличия подписки у донора."""
    basic_encoded = base64.b64encode(
        f"{settings.CLOUDPAYMENTS_PUBLIC_ID}:"
        f"{settings.CLOUDPAYMENTS_API_SECRET}".encode(),
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {basic_encoded}"}
    body = {"accountId": f"{email}"}
    response = http_client.request(
        method="POST",
        url=settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL,
        headers=headers,
        json=body,
    )
    return (
        SubscriptionStatuses.ACTIVE.capitalized
        if response.json()["Model"]
        else SubscriptionStatuses.INACTIVE.capitalized
    )


def handling_cloudpayment_data(request):
    """Формирование данных для сериализатора CloudpaymentsSerializer."""
    # Предполагаем, что request.data содержит json-объект,
    # т.е. ответ сервиса Cloudpayments при запросе на создании платежа.
    if isinstance(request.data, dict) and "Model" in request.data:
        model = request.data["Model"][0]
        data = {
            "email": model.get("Email"),
            "donat": model.get("Amount"),
            "date_created": model.get("CreatedDateIso"),
            "date_processed": model.get("ConfirmDateIso"),
            "payment_id": model.get("TransactionId"),
            "status": model.get("Status"),
            "payment_operator": "Cloudpayment",
            "payment_method": model.get("CardType"),
            "user_account_id": model.get("TransactionId"),
            "currency": model.get("Currency"),
        }
        subscription = check_donor_subscriptions(data["email"])
        create_or_update_donor(data, subscription)
        return data
    logger.info("Неправильная структура request.data")
    raise ValueError("Неправильная структура request.data")


def check_cloudpayments_connection():
    """Проверяет подключение к API CloudPayments."""
    url = settings.CLOUDPAYMENTS_API_TEST_URL
    headers = {"Content-Type": "application/json"}
    auth = (
        settings.CLOUDPAYMENTS_PUBLIC_ID,
        settings.CLOUDPAYMENTS_API_SECRET,
    )
    try:
        http_client.request(HTTPMethod.POST, url, headers=headers, auth=auth)
    except zapros.StatusCodeError as error:
        if error.response.status not in _CLOUDPAYMENTS_BAD_KEYS_STATUSES:
            raise
        logger.info(
            "Cloudpayments отклонил запрос, статус: %s",
            error.response.status,
        )
        return False
    return True
