"""Модуль бизнес логики Mixplat."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from donor_base.constants import (
    DATE_FORMAT,
    DEFAULT_TZ,
    SubscriptionStatuses,
)
from mixplat.models import MixPlat
from rest_framework import status
from rest_framework.response import Response

from api.donor_service import create_or_update_donor

logger = logging.getLogger(__name__)


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return datetime.strptime(value, DATE_FORMAT).replace(
        tzinfo=ZoneInfo(DEFAULT_TZ),
    )


def _build_mixplat_payload(data):
    """Формирует словарь данных Mixplat и определяет статус подписки."""
    mixplat_obj_dict = {
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


def mixplat_request_handler(request):
    """Метод создания объектов из данных от Mixplat."""
    try:
        mixplat_obj_dict, subscription = _build_mixplat_payload(request.data)
        create_or_update_donor(mixplat_obj_dict, subscription)
        MixPlat.objects.create(**mixplat_obj_dict)
        return Response({"result": "ok"}, status=status.HTTP_200_OK)
    except KeyError:
        return Response(
            {"result": "error", "error_description": "Internal error"},
            status=status.HTTP_400_BAD_REQUEST,
        )