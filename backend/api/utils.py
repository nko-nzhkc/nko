"""Модуль бизнес логики проекта."""

import base64
import csv
import logging
import os
import shutil
from datetime import datetime
from http import HTTPMethod, HTTPStatus

import zapros
from django.conf import settings
from django.db.models import F
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from contacts.models import Donor
from donor_base import http_client
from mixplat.models import MixPlat
from donor_base.constants import (
    BAD_PAYMENTS_COUNT, DATE_FORMAT,
    NEGATIVE_SUB_STAT,
    PaymentStatuses,
    SubscriptionStatuses
)
from donor_base.subscriptions import get_name_by_group_id


logger = logging.getLogger(__name__)

_CLOUDPAYMENTS_BAD_KEYS_STATUSES = frozenset(
    {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}
)


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return make_aware(datetime.strptime(value, DATE_FORMAT))


def donor_exists(email):
    """Метод проверки наличия контакта донора в ДБ."""
    return Donor.objects.filter(email=email).exists()


def ad_donor(donor, subscription, update=False):
    """Добавляет email донора в указанную группу в БД и в unisender."""
    Donor.objects.update_or_create(
        email=donor,
        defaults={"subscription": subscription, "count_declined": 0},
    )
    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "overwrite_lists": 1 if update else 0,
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "data[0][0]": donor,
        "data[0][1]": SubscriptionStatuses[subscription].group_id,
    }
    http_client.post_form(settings.IMPORT_UNISENDER, data)


def mixplat_request_handler(request):
    """Метод создания объектов из данных от Mixplat."""
    try:
        mixplat_obj_dict = dict(
            email=request.data["user_email"],
            donat=request.data["amount"],
            custom_donat=request.data["amount_user"],
            payment_method=request.data["payment_method"],
            payment_id=request.data["payment_id"],
            status=request.data["status"],
            user_account_id=request.data["user_account_id"],
            date_created=string_to_date(request.data["date_created"]),
            date_processed=string_to_date(request.data["date_processed"]),
            payment_operator="mixplat",
            currency=request.data["currency"],
        )

        if request.data.get("recurrent_id"):
            subscription = SubscriptionStatuses.ACTIVE.capitalized
        else:
            subscription = SubscriptionStatuses.INACTIVE.capitalized

        create_or_update_donor(mixplat_obj_dict, subscription)
        MixPlat.objects.create(**mixplat_obj_dict)

        return Response(dict(result="ok"), status=status.HTTP_200_OK)
    except KeyError:
        return Response(
            dict(result="error", error_description="Internal error"),
            status=status.HTTP_400_BAD_REQUEST,
        )


def check_donor_subscriptions(email):
    """Проверка наличия подписки у донора."""
    url = settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL
    username = settings.CLOUDPAYMENTS_PUBLIC_ID
    password = settings.CLOUDPAYMENTS_API_SECRET
    basic_encoded = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {basic_encoded}"}
    body = {"accountId": f"{email}"}
    response = http_client.request("POST", url, headers=headers, json=body)
    return (
        SubscriptionStatuses.ACTIVE.capitalized if response.json()["Model"]
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


def create_or_update_donor(data, subscription):
    """Создаем нового донора или обновляем статус существующего."""
    # Если донора нет в базе:
    if not donor_exists(data["email"]):
        # Если подписка неактивна:
        if subscription == SubscriptionStatuses.INACTIVE.capitalized:
            # Сохраняем как Inactive
            ad_donor(
                data["email"],
                SubscriptionStatuses.INACTIVE.capitalized,
            )
            logger.info(
                f"Создан Донор {data['email']} "
                f"{SubscriptionStatuses.INACTIVE.capitalized}"
            )
        # Если подписка активна:
        elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
            # Сохраняем как "Active"
            ad_donor(
                data["email"],
                SubscriptionStatuses.ACTIVE.capitalized,
            )
            # Отправляем донору письмо
            send_payment_email(
                data["email"],
                SubscriptionStatuses.ACTIVE.group_id,
            )
            logger.info(
                f"Создан Донор {data['email']} "
                f"{SubscriptionStatuses.ACTIVE.capitalized}"
            )
    # Если донор есть в базе смотрим статус платежа
    else:
        donor = Donor.objects.get(email=data["email"])
        # Если платеж неуспешный
        # и в базе статус активен
        if (
            data["status"] in PaymentStatuses
            and donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
        ):
            # если у донора 3й отклонённый платёж
            if donor.count_declined + 1 == BAD_PAYMENTS_COUNT:
                # Обновляем его статус на Lost
                ad_donor(
                    data["email"],
                    SubscriptionStatuses.LOST.capitalized,
                    "update",
                )
                logger.info(
                    f"У Донора {data['email']} обновлен статус "
                    f"на {SubscriptionStatuses.LOST.capitalized}"
                )
            else:
                Donor.objects.filter(email=data["email"]).update(
                    count_declined=F("count_declined") + 1
                )
        # Если платеж успешный, обновляем запись
        else:
            # если активная подписка
            # и старый статус "Lost", "Inactive"
            if (
                subscription == SubscriptionStatuses.ACTIVE.capitalized
                and donor.subscription in NEGATIVE_SUB_STAT
            ):
                # Обновляем его статус на "Active"
                ad_donor(
                    data["email"],
                    SubscriptionStatuses.ACTIVE.capitalized,
                    "update",
                )
                # Отправляем донору письмо
                send_payment_email(
                    data["email"],
                    SubscriptionStatuses.ACTIVE.group_id,
                )
                logger.info(
                    f"У Донора {data['email']} обновлен статус "
                    f"{SubscriptionStatuses.ACTIVE.capitalized}"
                )
            else:
                Donor.objects.filter(email=data["email"]).update(
                    count_declined=0
                )


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
            f"Cloudpayments отклонил запрос, статус: "
            f"{error.response.status}"
        )
        return False
    return True


def _extract_unisender_result(response_data, error_label="Ошибка:"):
    """Извлекает result из ответа Unisender."""
    if "error" in response_data:
        logger.info(error_label)
        logger.info(f"Код ошибки: {response_data['code']}")
        logger.info(f"Сообщение об ошибке: {response_data['error']}")
        return None
    if "result" in response_data:
        return response_data["result"]
    logger.info(f"Неизвестный ответ от сервера: {response_data}")
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
        response.json, "Ошибка при запросе шаблона:"
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
        response.json, "Ошибка при отправке сообщения:"
    )
    if result is not None:
        logger.info("Сообщение успешно отправлено!")
        logger.info(f"Email ID: {result['email_id']}")


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
    logger.info(f"result: {result}")
    return response_data


def add_contacts(file_url):
    """Добавление доноров в БД из файла, получаемого по ссылке."""
    response = http_client.request(HTTPMethod.GET, file_url)
    if response.status != HTTPStatus.OK:
        message = (
            f"Файл по ссылке не получен, код ответа {response.status}."
        )
        logger.info(message)
        return message

    bulk_list = list()
    directory = "files"
    if not os.path.exists(directory):
        os.makedirs(directory)
    file_path = os.path.join(directory, "data.csv")

    with open(file_path, "wb") as file:
        file.write(response.read())

    with open(file_path, encoding="utf-8") as csv_file:
        file_reader = csv.reader(csv_file, delimiter=",")
        for row in file_reader:
            if row[0] != "email" and donor_exists(row[0]) is False:
                bulk_list.append(
                    Donor(
                        email=row[0],
                        subscription=get_name_by_group_id(row[1])
                    ),
                )
        Donor.objects.bulk_create(bulk_list)

    try:
        shutil.rmtree(directory)  # удаляем папку с файлом
    except OSError as e:
        raise f"Error: {e.filename, e.strerror}"

    logger.info(f"Добавлено {len(bulk_list)} контактов.")
    return f"Добавлено {len(bulk_list)} контактов."
