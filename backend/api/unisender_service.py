"""Модуль бизнес логики Unisender."""

import logging
import pathlib
import shutil
from collections import Counter
from csv import DictReader
from http import HTTPMethod, HTTPStatus
from typing import Any

from django.conf import settings

from contacts.models import Donor
from donor_base import http_client
from donor_base.constants import UnisenderExpectedFilenames
from donor_base.subscriptions import get_capitalized_by_group_id


logger = logging.getLogger(__name__)


def _extract_unisender_result(
    response_data: dict[str, Any],
    error_label: str = "Ошибка:",
) -> Any | None:
    """Извлекает result из ответа Unisender."""
    if "error" in response_data:
        logger.info(error_label)
        logger.info("Код ошибки: %s", response_data.get("code"))
        logger.info("Сообщение об ошибке: %s", response_data.get("error"))
        return None
    unisender_result = response_data.get("result")
    if unisender_result is not None:
        return unisender_result
    logger.info("Неизвестный ответ от сервера: %s", response_data)
    return None


def send_payment_email(email: str, list_id: int | str) -> None:
    """Получение шаблона и отправка письма донору."""
    template_data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "template_id": settings.TEMPLATE_ID,
    }
    response = http_client.post_form(settings.URL_GET_TEMP, template_data)
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
    unisender_result = _extract_unisender_result(
        response.json,
        "Ошибка при отправке сообщения:",
    )
    if unisender_result is not None:
        logger.info("Сообщение успешно отправлено!")
        logger.info("Email ID: %s", unisender_result["email_id"])


def send_request(list_id: int | str) -> dict[str, Any] | None:
    """Отправка запроса на получение контактов доноров от Unisender."""
    data = {
        "api_key": settings.UNISENDER_API_KEY,
        "notify_url": settings.NOTIFY_URL,
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "list_id": list_id,
    }
    response = http_client.post_form(settings.EXPORT_UNISENDER, data)
    response_data: dict[str, Any] = response.json
    unisender_result = _extract_unisender_result(response_data)
    if unisender_result is None:
        return None
    logger.info("Успешно!")
    logger.info("result: %s", unisender_result)
    return response_data


def _save_file_from_url(file_url: str, file_path: pathlib.Path) -> str | None:
    """Скачивает файл по ссылке и сохраняет локально.

    Возвращает сообщение об ошибке или None.
    """
    response = http_client.request(HTTPMethod.GET, file_url)
    if response.status != HTTPStatus.OK:
        return f"Файл по ссылке не получен, код ответа {response.status}."
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(response.read())
    return None


def _get_new_emails(emails: list[str]) -> set[str]:
    """Формирует недублированный список email по данным БД.

    По списку email из файла от Юнисендера получаем список совпадающих.
    Отдаем разницу между изначальным списком и существующим.
    """
    existing_emails = set(
        Donor.objects.filter(email__in=emails).values_list(
            "email",
            flat=True,
        ),
    )
    return set(emails) - existing_emails


def _has_duplicate_emails(emails: list[str]) -> bool:
    """Проверяет наличие дублей email в файле от Юнисендера."""
    counts = Counter(emails)
    duplicates = {email for email, count in counts.items() if count > 1}
    if duplicates:
        logger.warning(
            "В исходном файле обнаружены дубли email: %s",
            duplicates,
        )
        return True
    return False


def _has_missing_columns(fieldnames: list[str] | None) -> bool:
    """Проверяет шапку файла от Юнисендера."""
    if not fieldnames:
        logger.warning(
            "В исходном файле не обнаружены заголовки.",
        )
        return True

    missing_fieldnames = {
        field.value for field in UnisenderExpectedFilenames
    } - set(fieldnames)

    if missing_fieldnames:
        logger.warning(
            "В исходном файле отсутствуют ожидаемые поля: %s",
            missing_fieldnames,
        )
    return bool(missing_fieldnames)


def _build_bulk_list(file_path: pathlib.Path) -> list[Donor]:
    """Формирует список новых доноров из CSV-файла."""
    with file_path.open(encoding="utf-8") as csv_file:
        reader = DictReader(csv_file, delimiter=",")
        if _has_missing_columns(reader.fieldnames):
            raise ValueError(
                "Ошибка при обработке исходного файла: "
                "шапка не соответствует ожидаемой.",
            )
        rows = list(reader)
        emails = [row[UnisenderExpectedFilenames.EMAIL.value] for row in rows]

        if _has_duplicate_emails(emails):
            raise ValueError(
                "Ошибка при обработке исходного файла: дубли email.",
            )
        emails = _get_new_emails(emails)

        return [
            Donor(
                email=row[UnisenderExpectedFilenames.EMAIL.value],
                subscription=get_capitalized_by_group_id(
                    row[UnisenderExpectedFilenames.EMAIL_STATUS.value],
                ),
            )
            for row in rows
            if row[UnisenderExpectedFilenames.EMAIL.value] in emails
        ]


def add_contacts(file_url: str) -> str | None:
    """Добавление доноров в БД из файла, получаемого по ссылке."""
    file_path = pathlib.Path("files") / "data.csv"

    error_message = _save_file_from_url(file_url, file_path)
    if error_message:
        logger.info(error_message)
        return error_message

    bulk_list = _build_bulk_list(file_path)
    Donor.objects.bulk_create(bulk_list)

    try:
        shutil.rmtree(file_path.parent)
    except OSError as error:
        raise OSError(f"Error: {error.filename} - {error.strerror}") from error

    logger.info("Добавлено %s контактов.", len(bulk_list))
    return f"Добавлено {len(bulk_list)} контактов."
