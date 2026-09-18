"""Тесты репозиториев API."""

import pytest

from api.repositories import DonorRepository
from contacts.models import Donor


@pytest.fixture
def donors(db, faker, settings):
    """Создаёт доноров с разными статусами подписки."""
    return [
        Donor.objects.create(
            email=faker.unique.email(),
            subscription=subscription,
        )
        for subscription, _ in settings.SUBSCRIPTION_CHOICES[:2]
    ]


@pytest.mark.parametrize(
    "selection",
    ["all", "selected", "empty", "missing"],
)
def test_get_donors_returns_email_and_subscription(donors, selection):
    """Репозиторий возвращает данные, нужные use case."""
    if selection == "all":
        donor_ids = None
        expected_donors = donors
    elif selection == "selected":
        donor_ids = [donors[0].pk]
        expected_donors = donors[:1]
    elif selection == "empty":
        donor_ids = []
        expected_donors = []
    else:
        donor_ids = [max(donor.pk for donor in donors) + 1]
        expected_donors = []

    actual = list(
        DonorRepository().get_donors(donor_ids=donor_ids)
    )
    expected = [
        (donor.email, donor.subscription)
        for donor in expected_donors
    ]

    assert sorted(actual) == sorted(expected)
