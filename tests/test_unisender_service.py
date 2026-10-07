"""Тесты обработки CSV от Unisender."""

from collections.abc import Callable
from pathlib import Path

import pytest
from faker import Faker

from api.unisender_service import (
    _has_missing_columns,
    _build_bulk_list,
    _get_new_emails,
    _has_duplicate_emails,
)

from contacts.models import Donor
from donor_base.constants import (
    SubscriptionStatuses,
    UnisenderExpectedFilenames,
)


# ================= _has_missing_columns ==================

def test_has_missing_columns_none() -> None:
    """Тест на отсутствие колонок - None."""
    assert _has_missing_columns(None) is True


def test_has_missing_columns_empty_list() -> None:
    """Тест на отсутствие колонок - пустой лист."""
    assert _has_missing_columns([]) is True


def test_has_missing_columns_all_present() -> None:
    """Тест на совпадение шапки с ожидаемым."""
    assert _has_missing_columns([
        UnisenderExpectedFilenames.EMAIL.value,
        UnisenderExpectedFilenames.EMAIL_STATUS.value,
    ]) is False


def test_has_missing_columns_only_email() -> None:
    """Тест на отсутствие колонки статуса."""
    assert _has_missing_columns([
        UnisenderExpectedFilenames.EMAIL.value,
    ]) is True


def test_has_missing_columns_only_email_status() -> None:
    """Тест на отсутствие колонки адреса."""
    assert _has_missing_columns([
        UnisenderExpectedFilenames.EMAIL_STATUS.value,
    ]) is True


def test_has_missing_columns_wrong_columns() -> None:
    """Тест на несовпадающие с ожидаемыми колонки."""
    assert _has_missing_columns(["someth1ng", "w1ld"]) is True


# ================= _hes_duplicate_emails =================

def test_has_duplicate_emails_empty_list() -> None:
    """Тест на пустой лист."""
    assert _has_duplicate_emails([]) is False


def test_has_duplicate_emails_single_email() -> None:
    """Тест на один адрес."""
    assert _has_duplicate_emails(["a_@mail.ru"]) is False


def test_has_duplicate_emails_unique_emails() -> None:
    """Тест на несколько адресов без дублей."""
    assert _has_duplicate_emails([
        "a_@mail.ru",
        "b_@mail.ru",
    ]) is False


def test_has_duplicate_emails_two_same() -> None:
    """Тест на несколько адресов с дублями."""
    assert _has_duplicate_emails([
        "a_@mail.ru",
        "a_@mail.ru",
    ]) is True


def test_has_duplicate_emails_three_with_duplicate() -> None:
    """Тест на несколько адресов с дублями и без."""
    assert _has_duplicate_emails([
        "a_@mail.ru",
        "b_@mail.ru",
        "a_@mail.ru",
    ]) is True


# ==================== _get_new_emails ====================

def test_get_new_emails_returns_empty_for_empty_input(db: object) -> None:
    """Тест пустого ответа из БД при пустом запросе."""
    assert _get_new_emails([]) == set()


def test_get_new_emails_returns_empty_when_all_exists(db: object) -> None:
    """Тест пустого ответа при совпадении всех адресов с существующими."""
    Donor.objects.create(
        email="a_@mail.ru",
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert _get_new_emails(["a_@mail.ru"]) == set()


def test_get_new_emails_returns_all_when_db_empty(db: object) -> None:
    """Тест ответа со всеми адресами из входа, если их нет в БД."""
    emails = ["a_@mail.ru", "b_@mail.ru"]
    assert _get_new_emails(emails) == set(emails)


def test_get_new_emails_returns_excludes_existing(db: object) -> None:
    """Тест исключения адресов из создания, если уже присутствуют в базе."""
    Donor.objects.create(
        email="a_@mail.ru",
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert _get_new_emails(["a_@mail.ru", "b_@mail.ru"]) == {"b_@mail.ru"}


# ==================== _build_bulk_list ===================

@pytest.fixture
def csv_file(tmp_path: Path) -> Callable[[str], Path]:
    """Фабрика csv."""
    def _create(content: str) -> Path:
        path = tmp_path / "data.csv"
        path.write_text(content, encoding="utf-8")
        return path
    return _create


@pytest.fixture
def header() -> str:
    """Шапка csv на основании UnisenderExpectedFilenames."""
    return (
        f"{UnisenderExpectedFilenames.EMAIL.value},"
        f"{UnisenderExpectedFilenames.EMAIL_STATUS.value}"
    )


def test_build_bulk_list_maps_group_ids_to_subscriptions(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
    faker: Faker,
) -> None:
    """Тест маппинга group_id из CSV в capitalized статус."""
    active_id = SubscriptionStatuses.ACTIVE.group_id
    inactive_id = SubscriptionStatuses.INACTIVE.group_id
    email_active = faker.unique.email()
    email_inactive = faker.unique.email()

    path = csv_file(
        f"{header}\n"
        f"{email_active},{active_id}\n"
        f"{email_inactive},{inactive_id}\n",
    )
    result = _build_bulk_list(path)

    by_email = {donor.email: donor for donor in result}
    assert by_email[email_active].subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )
    assert by_email[email_inactive].subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )


def test_build_bulk_list_raises_on_missing_columns(
    db: object,
    csv_file: Callable[[str], Path],
) -> None:
    """Тест вылета с ValueError, если нет ожидаемых колонок."""
    path = csv_file("someth1ng,w1ld\na_@mail.ru,5\n")

    with pytest.raises(ValueError, match="шапка не соответствует ожидаемой"):
        _build_bulk_list(path)


def test_build_bulk_list_raises_on_duplicates(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
    faker: Faker,
) -> None:
    """Тест вылета с ValueError, если есть дубли email в CSV."""
    email = faker.unique.email()
    active_id = SubscriptionStatuses.ACTIVE.group_id

    path = csv_file(
        f"{header}\n"
        f"{email},{active_id}\n"
        f"{email},{active_id}\n",
    )

    with pytest.raises(ValueError, match="дубли email"):
        _build_bulk_list(path)


def test_build_bulk_list_returns_empty_for_header_only(
    db: object,
    csv_file: Callable[[str], Path],
    header: str,
) -> None:
    """Тест пустого значения при обработке csv без полей кроме шапки."""
    path = csv_file(f"{header}\n")

    assert _build_bulk_list(path) == []
