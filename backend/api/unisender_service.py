"""Модуль бизнес логики Unisender."""

import csv
import logging
import pathlib
import shutil
from http import HTTPMethod, HTTPStatus

from django.conf import settings
from donor_base import http_client
from donor_base.subscriptions import get_capitalized_by_group_id
from contacts.models import Donor

from api.donor_service import donor_exists

logger = logging.getLogger(__name__)


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