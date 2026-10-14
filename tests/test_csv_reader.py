from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Final

import pytest
from faker import Faker

from api.unisender_service.csv_reader import (
    build_bulk_list,
    get_new_emails,
    has_duplicate_emails,
    has_missing_columns,
)
from contacts.models import Donor
from donor_base.constants import (
    SubscriptionStatuses,
    UnisenderExpectedFilenames,
)

EMAIL_A: Final = "a_@mail.ru"
EMAIL_B: Final = "b_@mail.ru"


@pytest.mark.parametrize(
    ("fieldnames", "expected_has_missing"),
    [
        (None, True),
        ([], True),
        (
            [
                UnisenderExpectedFilenames.EMAIL.value,
                UnisenderExpectedFilenames.EMAIL_STATUS.value,
            ],
            False,
        ),
        ([UnisenderExpectedFilenames.EMAIL.value], True),
        ([UnisenderExpectedFilenames.EMAIL_STATUS.value], True),
        (["someth1ng", "w1ld"], True),
    ],
)
def test_has_missing_columns(
    *,
    fieldnames: list[str] | None,
    expected_has_missing: bool,
) -> None:
    """Тест проверки шапки файла Юнисендера."""
    assert has_missing_columns(fieldnames) is expected_has_missing


@pytest.mark.parametrize(
    ("emails", "expected_has_double"),
    [
        ([], False),
        ([EMAIL_A], False),
        ([EMAIL_A, EMAIL_B], False),
        ([EMAIL_A, EMAIL_A], True),
        ([EMAIL_A, EMAIL_B, EMAIL_A], True),
    ],
)
def test_hes_duplicate_emails(
    *,
    emails: list[str],
    expected_has_double: bool,
) -> None:
    """Тест проверки дублей по email в файле Юнисендера."""
    assert has_duplicate_emails(emails) is expected_has_double


@pytest.mark.django_db
def test_get_new_emails_empty_input() -> None:
    """Тест пустого ответа из БД при пустом запросе."""
    assert get_new_emails([]) == set()


@pytest.mark.django_db
def test_get_new_emails_all_exists() -> None:
    """Тест пустого ответа при совпадении всех адресов с существующими."""
    Donor.objects.create(
        email=EMAIL_A,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert get_new_emails([EMAIL_A]) == set()


@pytest.mark.django_db
def test_get_new_emails_returns_all_when_db_empty() -> None:
    """Тест ответа со всеми адресами из входа, если их нет в БД."""
    emails = [EMAIL_A, EMAIL_B]
    assert get_new_emails(emails) == set(emails)


@pytest.mark.django_db
def test_get_new_emails_returns_excludes_existing() -> None:
    """Тест исключения адресов из создания, если уже присутствуют в базе."""
    Donor.objects.create(
        email=EMAIL_A,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    assert get_new_emails([EMAIL_A, EMAIL_B]) == {EMAIL_B}


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
def csv_with_two_statuses(
    csv_file: Callable[[str], Path],
    header: str,
    faker: Faker,
) -> tuple[Path, str, str]:
    """Создаёт CSV с двумя разными донорами и статусами."""
    active_id = SubscriptionStatuses.ACTIVE.group_id
    inactive_id = SubscriptionStatuses.INACTIVE.group_id
    email_active = faker.unique.email()
    email_inactive = faker.unique.email()

    path = csv_file(
        f"{header}\n"
        f"{email_active},{active_id}\n"
        f"{email_inactive},{inactive_id}\n",
    )
    return path, email_active, email_inactive


@pytest.mark.django_db
def test_build_bulk_list_maps_group_ids(
    csv_with_two_statuses: tuple[Path, str, str],
) -> None:
    """Тест маппинга group_id из CSV в capitalized статус."""
    path, email_active, email_inactive = csv_with_two_statuses
    donors = build_bulk_list(path)

    by_email = {donor.email: donor for donor in donors}
    assert by_email[email_active].subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )
    assert by_email[email_inactive].subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )


@pytest.mark.django_db
def test_build_bulk_list_missing_columns(
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
