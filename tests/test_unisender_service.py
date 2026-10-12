"""Тесты обработки CSV от Unisender."""

from collections.abc import Callable
from functools import partial
from http import HTTPMethod, HTTPStatus
from pathlib import Path
from typing import Any

import pytest
import zapros
from faker import Faker
from pytest_django import Settings
from zapros.mock import Mock

from api.unisender_service.contacts import add_contacts
from api.unisender_service.csv_reader import (
    build_bulk_list,
    get_new_emails,
    has_duplicate_emails,
    has_missing_columns,
)
from api.unisender_service.email_sender import (
    send_payment_email,
    send_request,
)
from contacts.models import Donor
from donor_base.constants import (
    SubscriptionStatuses,
    UnisenderExpectedFilenames,
)


EMAIL_A = "a_@mail.ru"
EMAIL_B = "b_@mail.ru"


# ================= has_missing_columns ==================


def test_has_missing_columns_none() -> None:
    """Тест на отсутствие колонок - None."""
    assert has_missing_columns(None) is True


def test_has_missing_columns_empty_list() -> None:
    """Тест на отсутствие колонок - пустой лист."""
    assert has_missing_columns([]) is True


def test_has_missing_columns_all_present() -> None:
    """Тест на совпадение шапки с ожидаемым."""
    assert (
        has_missing_columns([
            UnisenderExpectedFilenames.EMAIL.value,
            UnisenderExpectedFilenames.EMAIL_STATUS.value,
        ])
        is False
    )


def test_has_missing_columns_only_email() -> None:
    """Тест на отсутствие колонки статуса."""
    assert (
        has_missing_columns([
            UnisenderExpectedFilenames.EMAIL.value,
        ])
        is True
    )


def test_has_missing_columns_only_email_status() -> None:
    """Тест на отсутствие колонки адреса."""
    assert (
        has_missing_columns([
            UnisenderExpectedFilenames.EMAIL_STATUS.value,
        ])
        is True
    )


def test_has_missing_columns_wrong_columns() -> None:
    """Тест на несовпадающие с ожидаемыми колонки."""
    assert has_missing_columns(["someth1ng", "w1ld"]) is True


# ================= has_duplicate_emails =================


def test_has_duplicate_emails_empty_list() -> None:
    """Тест на пустой лист."""
    assert has_duplicate_emails([]) is False


def test_has_duplicate_emails_single_email() -> None:
    """Тест на один адрес."""
    assert has_duplicate_emails([EMAIL_A]) is False


def test_has_duplicate_emails_unique_emails() -> None:
    """Тест на несколько адресов без дублей."""
    assert (
        has_duplicate_emails([
            EMAIL_A,
            EMAIL_B,
        ])
        is False
    )


def test_has_duplicate_emails_two_same() -> None:
    """Тест на несколько адресов с дублями."""
    assert (
        has_duplicate_emails([
            EMAIL_A,
            EMAIL_A,
        ])
        is True
    )


def test_has_duplicate_emails_with_duplicate() -> None:
    """Тест на несколько адресов с дублями и без."""
    assert (
        has_duplicate_emails([
            EMAIL_A,
            EMAIL_B,
            EMAIL_A,
        ])
        is True
    )


# ==================== get_new_emails ====================


def test_get_new_emails_empty_input(db: object) -> None:
    """Тест пустого ответа из БД при пустом запросе."""
    assert get_new_emails([]) == set()


def test_get_new_emails_all_exists(db: object) -> None:
    """Тест пустого ответа при совпадении всех адресов с существующими."""
    Donor.objects.create(
        email=EMAIL_A,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert get_new_emails([EMAIL_A]) == set()


def test_get_new_emails_returns_all_when_db_empty(db: object) -> None:
    """Тест ответа со всеми адресами из входа, если их нет в БД."""
    emails = [EMAIL_A, EMAIL_B]
    assert get_new_emails(emails) == set(emails)


def test_get_new_emails_returns_excludes_existing(db: object) -> None:
    """Тест исключения адресов из создания, если уже присутствуют в базе."""
    Donor.objects.create(
        email=EMAIL_A,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert get_new_emails([EMAIL_A, EMAIL_B]) == {EMAIL_B}


# ==================== build_bulk_list ===================


def _create_csv(tmp_path: Path, csv_content: str) -> Path:
    """Создаёт CSV-файл."""
    path = tmp_path / "data.csv"
    path.write_text(csv_content, encoding="utf-8")
    return path


@pytest.fixture
def csv_file(tmp_path: Path) -> Callable[[str], Path]:
    """Фабрика csv."""
    return partial(_create_csv, tmp_path)


@pytest.fixture
def header() -> str:
    """Шапка csv на основании UnisenderExpectedFilenames."""
    email_field = UnisenderExpectedFilenames.EMAIL.value
    status_field = UnisenderExpectedFilenames.EMAIL_STATUS.value
    return f"{email_field},{status_field}"


@pytest.fixture
def bulk_list_result(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
    faker: Faker,
) -> tuple[list[Donor], str, str]:
    """Создаёт CSV и возвращает результат build_bulk_list."""
    active_id = SubscriptionStatuses.ACTIVE.group_id
    inactive_id = SubscriptionStatuses.INACTIVE.group_id
    email_active = faker.unique.email()
    email_inactive = faker.unique.email()

    path = csv_file(
        f"{header}\n"
        f"{email_active},{active_id}\n"
        f"{email_inactive},{inactive_id}\n",
    )
    return build_bulk_list(path), email_active, email_inactive


def test_build_bulk_list_maps_group_ids(
    bulk_list_result: tuple[list[Donor], str, str],
) -> None:
    """Тест маппинга group_id из CSV в capitalized статус."""
    donors, email_active, email_inactive = bulk_list_result

    by_email = {donor.email: donor for donor in donors}
    assert by_email[email_active].subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )
    assert by_email[email_inactive].subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )


def test_build_bulk_list_missing_columns(
    db: object,
    csv_file: Callable[[str], Path],
) -> None:
    """Тест вылета с ValueError, если нет ожидаемых колонок."""
    path = csv_file(f"someth1ng,w1ld\n{EMAIL_A},5\n")

    with pytest.raises(ValueError, match="шапка не соответствует ожидаемой"):
        build_bulk_list(path)


def test_build_bulk_list_raises_on_duplicates(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
    faker: Faker,
) -> None:
    """Тест вылета с ValueError, если есть дубли email в CSV."""
    email = faker.unique.email()
    active_id = SubscriptionStatuses.ACTIVE.group_id

    path = csv_file(f"{header}\n{email},{active_id}\n{email},{active_id}\n")

    with pytest.raises(ValueError, match="дубли email"):
        build_bulk_list(path)


def test_build_bulk_list_header_only(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
) -> None:
    """Тест пустого значения при обработке csv без полей кроме шапки."""
    path = csv_file(f"{header}\n")

    assert build_bulk_list(path) == []


# ========================================================
# ===== Тесты ошибок Unisender и скачивания CSV.""" ======
# ========================================================


@pytest.mark.parametrize(
    "response_data",
    [
        {"error": "bad request", "code": 400},
        {"unexpected": "payload"},
    ],
)
def test_send_request_none_for_error_payloads(
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    *,
    response_data: dict[str, Any],
) -> None:
    """Error и неизвестный JSON обрабатываются через публичный сервис."""
    route_zapros_response(
        HTTPMethod.POST,
        settings.EXPORT_UNISENDER,
        zapros.Response(
            status=HTTPStatus.OK,
            json=response_data,
        ),
    )

    assert send_request("5") is None


def test_send_email_stops_without_template(
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """При отсутствии шаблона запрос sendEmail не выполняется."""
    template_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_GET_TEMP,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"error": "template not found", "code": 404},
        ),
    )

    send_payment_email("donor@example.org", "5")

    template_route.assert_called_once()


def test_send_payment_email_handles_send_error(
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Ошибка sendEmail обрабатывается после получения шаблона."""
    template_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_GET_TEMP,
        zapros.Response(
            status=HTTPStatus.OK,
            json={
                "result": {
                    "subject": "Thank you",
                    "body": "Payment received",
                },
            },
        ),
    )
    email_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_SEND_EMAIL,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"error": "invalid email", "code": 400},
        ),
    )

    send_payment_email("donor@example.org", "5")

    template_route.assert_called_once()
    email_route.assert_called_once()


@pytest.mark.django_db
def test_add_contacts_not_found_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """HTTP 404 отбрасывается raise_for_status до проверки status."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/missing.csv"
    route = route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NOT_FOUND),
    )

    with pytest.raises(zapros.StatusCodeError) as caught:
        add_contacts(file_url)

    assert caught.value.response.status == HTTPStatus.NOT_FOUND
    route.assert_called_once()


@pytest.mark.django_db
def test_add_contacts_no_content_returns_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """204 проходит raise_for_status и доходит до проверки status == 200."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/empty.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NO_CONTENT),
    )

    assert add_contacts(file_url) == (
        "Файл по ссылке не получен, код ответа 204."
    )
    assert not (tmp_path / "files").exists()


@pytest.mark.django_db
def test_import_new_donors_reuses_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    header: str,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Существующий каталог переиспользуется, новые доноры импортируются."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "files").mkdir()
    email = faker.unique.email()
    inactive_group_id = SubscriptionStatuses.INACTIVE.group_id
    csv_data = (f"{header}\n{email},{inactive_group_id}\n").encode()
    file_url = "https://files.test/contacts.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(
            status=HTTPStatus.OK,
            content=csv_data,
        ),
    )

    assert add_contacts(file_url) == "Добавлено 1 контактов."
    assert Donor.objects.get(email=email).subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )
    assert not (tmp_path / "files").exists()
