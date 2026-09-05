"""Модуль бизнес логики проекта."""

import base64
import csv
import http
import logging
import os
import shutil
from datetime import datetime

import zapros
from django.conf import settings
from django.db.models import F
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from contacts.models import Donor
from donor_base import http_client
from mixplat.models import MixPlat

logger = logging.getLogger(__name__)


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return make_aware(datetime.strptime(value, settings.DATE_FORMAT))


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
        "data[0][1]": settings.GROUPS[subscription],
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
            subscription = settings.SUBSCRIPTION_CHOICES[0][0]
        else:
            subscription = settings.SUBSCRIPTION_CHOICES[1][0]

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
    if response.json["Model"]:
        return settings.SUBSCRIPTION_CHOICES[0][0]
    return settings.SUBSCRIPTION_CHOICES[1][0]


def handling_cloudpayment_data(request):
    """Формирование данных для сериалайзера CloudpaymentsSerializer."""
    # Предлполагаем, что request.data содержит json-объект,
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
        if subscription == settings.SUBSCRIPTION_CHOICES[1][0]:
            # Сохраняем как Inactive
            ad_donor(
                data["email"],
                settings.SUBSCRIPTION_CHOICES[1][0],
            )
            logger.info(
                f"Создан Донор {data['email']} "
                f"{settings.SUBSCRIPTION_CHOICES[1][0]}"
            )
        # Если подписка активна:
        elif subscription == settings.SUBSCRIPTION_CHOICES[0][0]:
            # Сохраняем как "Active"
            ad_donor(
                data["email"],
                settings.SUBSCRIPTION_CHOICES[0][0],
            )
            # Отправляем донору письмо
            send_payment_email(
                data["email"],
                settings.GROUPS[settings.SUBSCRIPTION_CHOICES[0][0]],
            )
            logger.info(
                f"Создан Донор {data['email']} "
                f"{settings.SUBSCRIPTION_CHOICES[0][0]}"
            )
    # Если донор есть в базе смотрим статус платежа
    else:
        donor = Donor.objects.get(email=data["email"])
        # Если платеж неуспешный
        if data["status"] in settings.BAD_STATUSES:
            # Если в базе статус активен
            if donor.subscription == settings.SUBSCRIPTION_CHOICES[0][0]:
                # если у донора 3й откланённый платёж
                if donor.count_declined + 1 == settings.BAD_COUNT:
                    # Обновляем его статус на Lost
                    ad_donor(
                        data["email"],
                        settings.SUBSCRIPTION_CHOICES[2][0],
                        "update",
                    )
                    logger.info(
                        f"У Донора {data['email']} обновлен статус "
                        f"на {settings.SUBSCRIPTION_CHOICES[2][0]}"
                    )
                else:
                    Donor.objects.filter(email=data["email"]).update(
                        count_declined=F("count_declined") + 1
                    )
        # Если платеж успешный, обновляем запись
        else:
            # если активная подписка
            if subscription == settings.SUBSCRIPTION_CHOICES[0][0]:
                # если старый статус "Lost", "Inactive"
                if donor.subscription in settings.NEY_SUB_STAT:
                    # Обновляем его статус на "Active"
                    ad_donor(
                        data["email"],
                        settings.SUBSCRIPTION_CHOICES[0][0],
                        "update",
                    )
                    # Отправляем донору письмо
                    send_payment_email(
                        data["email"],
                        settings.GROUPS[settings.SUBSCRIPTION_CHOICES[0][0]],
                    )
                    logger.info(
                        f"У Донора {data['email']} обновлен статус "
                        f"{settings.SUBSCRIPTION_CHOICES[0][0]}"
                    )
                else:
                    Donor.objects.filter(email=data["email"]).update(
                        count_declined=0
                    )
            else:
                Donor.objects.filter(email=data["email"]).update(
                    count_declined=0
                )


def check_cloudpayments_connection():
    """Проверка подключения к api cloudpayments."""
    url = settings.CLOUDPAYMENTS_API_TEST_URL
    headers = {"Content-Type": "application/json"}
    auth = (
        settings.CLOUDPAYMENTS_PUBLIC_ID,
        settings.CLOUDPAYMENTS_API_SECRET,
    )
    try:
        response = http_client.request("POST", url, headers=headers, auth=auth)
    except zapros.StatusCodeError:
        return False
    return response.status == http.HTTPStatus.OK


def send_payment_email(email, list_id):
    """Получение шаблона и отправка письма донору."""
    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "template_id": settings.TEMPLATE_ID,
    }
    response = http_client.post_form(settings.URL_GET_TEMP, data)
    res = response.json["result"]

    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "email": email,
        "sender_email": settings.DEFAULT_FROM_EMAIL,
        "sender_name": settings.UNISENDER_SENDER_NAME,
        "subject": res["subject"],
        "body": res["body"],
        "list_id": list_id,
    }
    response = http_client.post_form(settings.URL_SEND_EMAIL, data)
    response_data = response.json
    if "error" in response_data:
        logger.info("Ошибка при отправке сообщения:")
        logger.info(f"Код ошибки: {response_data['code']}")
        logger.info(f"Сообщение об ошибке: {response_data['error']}")
    elif "result" in response_data:
        logger.info("Сообщение успешно отправлено!")
        logger.info(f"Email ID: {response_data['result']['email_id']}")
    else:
        logger.info(f"Неизвестный ответ от сервера: {response_data}")


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
    if "error" in response_data:
        logger.info("Ошибка:")
        logger.info(f"Код ошибки: {response_data['code']}")
        logger.info(f"Сообщение об ошибке: {response_data['error']}")
    elif "result" in response_data:
        logger.info("Успешно!")
        logger.info(f"result: {response_data['result']}")
        return response_data
    else:
        logger.info(f"Неизвестный ответ от сервера: {response_data}")


def add_contacts(file_url):
    """Добавление доноров в БД из файла, получаемого по ссылке."""
    response = http_client.request("GET", file_url)
    if response.status == status.HTTP_200_OK:
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
                            email=row[0], subscription=settings.GROUPS[row[1]]
                        ),
                    )
            Donor.objects.bulk_create(bulk_list)

        try:
            shutil.rmtree(directory)  # удаляем папку с файлом
        except OSError as e:
            raise f"Error: {e.filename, e.strerror}"

        logger.info(f"Добавленно {len(bulk_list)} контактов.")
        return f"Добавленно {len(bulk_list)} контактов."
    logger.info(
        f"Файл по ссылке не получен, код ответа {response.status}"
    )
    return f"Файл по ссылке не получен, код ответа {response.status}."
