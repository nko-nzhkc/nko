"""Чтение и обработка CSV-файла от Unisender."""

import logging
import pathlib
from collections import Counter
from csv import DictReader
from http import HTTPMethod, HTTPStatus

from contacts.models import Donor
from donor_base import http_client
from donor_base.constants import UnisenderExpectedFilenames
from donor_base.subscriptions import get_capitalized_by_group_id

logger = logging.getLogger(__name__)


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