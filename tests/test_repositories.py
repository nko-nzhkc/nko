"""Тесты репозиториев API."""

import pytest

from api.repositories import DonorRepository
from contacts.models import Donor


@pytest.fixture
def donors(db, faker):
    """Создаёт доноров с разными статусами подписки."""
    return [
        Donor.objects.create(
            email=faker.unique.email(),
            subscription=subscription,
        )
        for subscription in ("Active", "Inactive")
    ]


def test_get_donors_returns_email_and_subscription(donors):
    """Репозиторий возвращает данные, нужные use case."""
    actual = list(DonorRepository().get_donors())
    expected = [
        (donor.email, donor.subscription)
        for donor in donors
    ]

    assert sorted(actual) == sorted(expected)


def test_get_donors_returns_only_selected_donor(donors):
    """Событие одного донора не выбирает остальных."""
    selected = donors[0]

    result = list(
        DonorRepository().get_donors(
            donor_ids=[selected.pk],
        )
    )

    assert result == [(selected.email, selected.subscription)]


def test_get_donors_with_empty_ids_returns_nothing(donors):
    """Пустой список не превращается в полную синхронизацию."""
    result = list(
        DonorRepository().get_donors(donor_ids=[])
    )

    assert result == []


def test_get_donors_with_missing_id_returns_nothing(donors):
    """Отсутствующий донор не приводит к отправке других."""
    missing_id = max(donor.pk for donor in donors) + 1

    result = list(
        DonorRepository().get_donors(
            donor_ids=[missing_id],
        )
    )

    assert result == []
