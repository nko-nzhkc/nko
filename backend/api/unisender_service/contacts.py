"""Точка входа: добавление контактов из файла."""

import logging
import pathlib
import shutil

from contacts.models import Donor

from .csv_reader import _build_bulk_list, _save_file_from_url

logger = logging.getLogger(__name__)


def add_contacts(file_url: str) -> str | None:
    """Добавление доноров в БД из файла по ссылке."""
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