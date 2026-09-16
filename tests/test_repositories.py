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
