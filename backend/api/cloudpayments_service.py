"""Модуль бизнес логики CloudPayments."""

import base64
import logging
from http import HTTPMethod, HTTPStatus
from typing import Any

import zapros
from django.conf import settings
from donor_base import http_client
from donor_base.constants import SubscriptionStatuses
from rest_framework.request import Request

from api.donor_service import create_or_update_donor

logger = logging.getLogger(__name__)

_CLOUDPAYMENTS_BAD_KEYS_STATUSES = frozenset(
    (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN),
)


def check_donor_subscriptions(email: str) -> str:
    """Проверка наличия подписки у донора."""
    basic_encoded = base64.b64encode(
        f"{settings.CLOUDPAYMENTS_PUBLIC_ID}:"
        f"{settings.CLOUDPAYMENTS_API_SECRET}".encode(),
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {basic_encoded}"}
    body = {"accountId": f"{email}"}
    response = http_client.request(
        method=HTTPMethod.POST,
        url=settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL,
        headers=headers,
        json=body,
    )
    return (
        SubscriptionStatuses.ACTIVE.capitalized
        if response.json()["Model"]
        else SubscriptionStatuses.INACTIVE.capitalized
    )


def handling_cloudpayment_data(request: Request) -> dict[str, Any]:
    """Формирование данных для сериализатора CloudpaymentsSerializer."""
    # Предполагаем, что request.data содержит json-объект,
    # т.е. ответ сервиса Cloudpayments при запросе на создании платежа.
    if isinstance(request.data, dict) and "Model" in request.data:
        model = request.data["Model"][0]
        data: dict[str, Any] = {
            "email": str(model.get("Email")),
            "donat": model.get("Amount"),
            "date_created": model.get("CreatedDateIso"),
            "date_processed": model.get("ConfirmDateIso"),
            "payment_id": model.get("TransactionId"),
            "status": str(model.get("Status")),
            "payment_operator": "Cloudpayment",
            "payment_method": model.get("CardType"),
            "user_account_id": model.get("TransactionId"),
            "currency": model.get("Currency"),
        }
        subscription = check_donor_subscriptions(data["email"])
        create_or_update_donor(
            donor_email=data["email"],
            payment_status=data["status"],
            subscription=subscription,
        )
        return data
    logger.info("Неправильная структура request.data")
    raise ValueError("Неправильная структура request.data")


def check_cloudpayments_connection() -> bool:
    """Проверяет подключение к API CloudPayments."""
    url = settings.CLOUDPAYMENTS_API_TEST_URL
    if url is None:
        return False
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
