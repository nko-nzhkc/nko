"""Модуль бизнес логики проекта."""

import base64
import csv
import logging
import pathlib
import shutil
from datetime import datetime
from functools import partial
from http import HTTPMethod, HTTPStatus
from zoneinfo import ZoneInfo

import zapros
from celery import chain
from contacts.models import Donor
from django.conf import settings
from django.db import transaction
from django.db.models import F
from donor_base import http_client
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    DATE_FORMAT,
    DEFAULT_TZ,
    NEGATIVE_SUB_STAT,
    FailedPaymentStatuses,
    SubscriptionStatuses,
)
from donor_base.subscriptions import (
    get_capitalized_by_group_id,
    get_group_by_capitalized,
)
from mixplat.models import MixPlat
from rest_framework import status
from rest_framework.response import Response

from api.tasks import (
    send_payment_email_task,
    send_users_to_unisender,
)

logger = logging.getLogger(__name__)

_CLOUDPAYMENTS_BAD_KEYS_STATUSES = frozenset(
    {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN},
)


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return datetime.strptime(value, DATE_FORMAT).replace(
        tzinfo=ZoneInfo(DEFAULT_TZ),
    )


def donor_exists(email):
    """Метод проверки наличия контакта донора в ДБ."""
    return Donor.objects.filter(email=email).exists()


def ad_donor(
    donor,
    subscription,
    update,
    *,
    send_email=False,
):
    """Сохраняет донора и планирует импорт, затем при необходимости письмо."""
    with transaction.atomic():
        donor_obj, _ = Donor.objects.update_or_create(
            email=donor,
            defaults={
                "subscription": subscription,
                "count_declined": 0,
            },
        )

        workflow = send_users_to_unisender.si(
            donor_ids=[donor_obj.pk],
            overwrite_lists=1 if update else 0,
        )

        if send_email:
            workflow = chain(
                workflow,
                send_payment_email_task.si(
                    email=donor_obj.email,
                    list_id=get_group_by_capitalized(subscription),
                ),
            )

        transaction.on_commit(
            partial(workflow.apply_async),
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


def check_donor_subscriptions(email):
    """Проверка наличия подписки у донора."""
    url = settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL
    username = settings.CLOUDPAYMENTS_PUBLIC_ID
    password = settings.CLOUDPAYMENTS_API_SECRET
    basic_encoded = base64.b64encode(
        f"{username}:{password}".encode(),
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {basic_encoded}"}
    body = {"accountId": f"{email}"}
    response = http_client.request("POST", url, headers=headers, json=body)
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


def _handle_failed_payment(data, donor):
    """Обрабатывает случай неуспешного платежа для существующего донора."""
    if donor.subscription == SubscriptionStatuses.ACTIVE.capitalized:
        # если у донора 3й отклонённый платёж
        if donor.count_declined + 1 == BAD_PAYMENTS_COUNT:
            ad_donor(
                data["email"],
                SubscriptionStatuses.LOST.capitalized,
                update=True,
            )
            logger.info(
                "У Донора %s обновлен статус на %s",
                {data["email"]},
                SubscriptionStatuses.LOST.capitalized,
            )
        else:
            Donor.objects.filter(email=data["email"]).update(
                count_declined=F("count_declined") + 1,
            )


def _handle_active_subscription(data, donor):
    """Обрабатывает случай успешного платежа с активной подпиской."""
    # если старый статус "Lost", "Inactive"
    if donor.subscription in NEGATIVE_SUB_STAT:
        ad_donor(
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
            update=True,
            send_email=True,
        )
        logger.info(
            "У Донора %s обновлен статус на %s",
            {data["email"]},
            SubscriptionStatuses.ACTIVE.capitalized,
        )
    else:
        Donor.objects.filter(email=data["email"]).update(
            count_declined=0,
        )


def _create_new_donor(data, subscription):
    """Создает нового донора в зависимости от статуса подписки."""
    if subscription == SubscriptionStatuses.INACTIVE.capitalized:
        ad_donor(
            data["email"],
            SubscriptionStatuses.INACTIVE.capitalized,
            update=False,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            data["email"],
            SubscriptionStatuses.INACTIVE.capitalized,
        )
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        ad_donor(
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
            update=False,
            send_email=True,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
        )


def _update_existing_donor(data, subscription):
    """Обновляет статус существующего донора в зависимости от платежа."""
    donor = Donor.objects.get(email=data["email"])
    if data["status"] in FailedPaymentStatuses:
        _handle_failed_payment(data, donor)
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        _handle_active_subscription(data, donor)
    else:
        Donor.objects.filter(email=data["email"]).update(
            count_declined=0,
        )


def create_or_update_donor(data, subscription):
    """Создаем нового донора или обновляем статус существующего."""
    if donor_exists(data["email"]):
        _update_existing_donor(data, subscription)
    else:
        _create_new_donor(data, subscription)


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


def _extract_unisender_result(response_data, error_label="Ошибка:"):
    """Извлекает result из ответа Unisender."""
    if "error" in response_data:
        logger.info(error_label)
        logger.info("Код ошибки: %s", response_data["code"])
        logger.info("Сообщение об ошибке: %s", response_data["error"])
        return None
    if "result" in response_data:
        return response_data["result"]
    logger.info("Неизвестный ответ от сервера: %s", response_data)
    return None


def send_payment_email(email, list_id):
    """Получение шаблона и отправка письма донору."""
    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "template_id": settings.TEMPLATE_ID,
    }
    response = http_client.post_form(settings.URL_GET_TEMP, data)
    template = _extract_unisender_result(
        response.json,
        "Ошибка при запросе шаблона:",
    )
    if template is None:
        return
    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "email": email,
        "sender_email": settings.DEFAULT_FROM_EMAIL,
        "sender_name": settings.UNISENDER_SENDER_NAME,
        "subject": template["subject"],
        "body": template["body"],
        "list_id": list_id,
    }
    response = http_client.post_form(settings.URL_SEND_EMAIL, data)
    result = _extract_unisender_result(
        response.json,
        "Ошибка при отправке сообщения:",
    )
    if result is not None:
        logger.info("Сообщение успешно отправлено!")
        logger.info("Email ID: %s", result["email_id"])


def send_request(list_id):
    """Отправка запроса на получение контактов доноров от Unisender."""
    data = {
        "api_key": settings.UNISENDER_API_KEY,
        "notify_url": settings.NOTIFY_URL,
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "list_id": list_id,
    }
    response = http_client.post_form(settings.EXPORT_UNISENDER, data)
    response_data = response.json
    result = _extract_unisender_result(response_data)
    if result is None:
        return None
    logger.info("Успешно!")
    logger.info("result: %s", result)
    return response_data


def add_contacts(file_url):
    """Добавление доноров в БД из файла, получаемого по ссылке."""
    response = http_client.request(HTTPMethod.GET, file_url)
    if response.status != HTTPStatus.OK:
        message = f"Файл по ссылке не получен, код ответа {response.status}."
        logger.info(message)
        return message

    bulk_list = []
    directory = "files"
    if not pathlib.Path(directory).exists():
        pathlib.Path(directory).mkdir(parents=True)
    file_path = pathlib.Path(directory) / "data.csv"

    file_path.write_bytes(response.read())

    with file_path.open(encoding="utf-8") as csv_file:
        file_reader = csv.reader(csv_file, delimiter=",")
        bulk_list.extend(
            Donor(
                email=row[0],
                subscription=get_capitalized_by_group_id(row[1]),
            )
            for row in file_reader
            if row[0] != "email" and donor_exists(row[0]) is False
        )
        Donor.objects.bulk_create(bulk_list)

    try:
        shutil.rmtree(directory)  # удаляем папку с файлом
    except OSError as e:
        raise OSError(f"Error: {e.filename, e.strerror}") from e

    logger.info("Добавлено %s контактов.", len(bulk_list))
    return f"Добавлено {len(bulk_list)} контактов."
