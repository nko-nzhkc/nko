"""Модуль бизнес логики Mixplat."""

import logging
from datetime import datetime
from typing import Any, TypedDict, TypeGuard
from zoneinfo import ZoneInfo

from donor_base.constants import (
    DATE_FORMAT,
    DEFAULT_TZ,
    SubscriptionStatuses,
)
from mixplat.models import MixPlat
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from api.donor_service import create_or_update_donor

logger = logging.getLogger(__name__)

ERROR_RESPONSE = Response(
    {"result": "error", "error_description": "Internal error"},
    status=status.HTTP_400_BAD_REQUEST,
)


class MixplatRequestData(TypedDict):
    """Класс реквеста Mixplat."""

    user_email: str
    amount: str
    amount_user: str
    payment_method: str
    payment_id: str
    status: str
    user_account_id: str
    date_created: str
    date_processed: str
    currency: str
    recurrent_id: str | None


class MixPlatPayload(TypedDict):
    """Полезная нагрузка для сохранения Mixplat/донора."""

    email: str
    donat: str
    custom_donat: str
    payment_method: str
    payment_id: str
    status: str
    user_account_id: str
    date_created: datetime
    date_processed: datetime
    payment_operator: str
    currency: str


def string_to_date(date_string: str) -> datetime:
    """Метод преобразования строки в дату, установка time-zone."""
    return datetime.strptime(date_string, DATE_FORMAT).replace(
        tzinfo=ZoneInfo(DEFAULT_TZ),
    )


def _is_mixplat_data(data: dict[Any, Any]) -> TypeGuard[MixplatRequestData]:
    """TypeGuard для mypy - сужает dict[Any,Any] до MixplatRequestData."""
    required_str_fields = (
        "user_email",
        "amount",
        "amount_user",
        "payment_method",
        "payment_id",
        "status",  # noqa: WPS226
        "user_account_id",
        "date_created",
        "date_processed",
        "currency",
    )
    for field in required_str_fields:
        if not isinstance(data.get(field), str):
            return False
    recurrent_id = data.get("recurrent_id")
    return not (recurrent_id is not None and not isinstance(recurrent_id, str))


def _build_mixplat_payload(
    data: MixplatRequestData,
) -> tuple[MixPlatPayload, str]:
    """Формирует словарь данных Mixplat и определяет статус подписки."""
    mixplat_obj_dict: MixPlatPayload = {
        "email": data["user_email"],
        "donat": data["amount"],
        "custom_donat": data["amount_user"],
        "payment_method": data["payment_method"],
        "payment_id": data["payment_id"],
        "status": data["status"],
        "user_account_id": data["user_account_id"],
        "date_created": string_to_date(data["date_created"]),
        "date_processed": string_to_date(data["date_processed"]),
        "payment_operator": "mixplat",
        "currency": data["currency"],
    }

    if data.get("recurrent_id"):
        subscription = SubscriptionStatuses.ACTIVE.capitalized
    else:
        subscription = SubscriptionStatuses.INACTIVE.capitalized

    return mixplat_obj_dict, subscription


def _process_mixplat_request(data: MixplatRequestData) -> None:
    """Обрабатывает данные запроса Mixplat и сохраняет объекты."""
    mixplat_obj_dict, subscription = _build_mixplat_payload(data)
    create_or_update_donor(
        donor_email=mixplat_obj_dict["email"],
        payment_status=mixplat_obj_dict["status"],
        subscription=subscription,
    )
    MixPlat.objects.create(**mixplat_obj_dict)


def mixplat_request_handler(request: Request) -> Response:
    """Метод создания объектов из данных от Mixplat."""
    data = request.data
    if not isinstance(data, dict):
        return ERROR_RESPONSE
    if not _is_mixplat_data(data):
        return ERROR_RESPONSE
    try:
        _process_mixplat_request(data)
    except KeyError:
        return ERROR_RESPONSE
    return Response({"result": "ok"}, status=status.HTTP_200_OK)
