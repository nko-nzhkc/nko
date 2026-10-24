"""Тесты репозиториев API."""

import pytest
from faker.proxy import Faker

from api.repositories import DonorRepository
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses


@pytest.fixture
def donors(db: object, faker: Faker) -> list[Donor]:
    """Создаёт доноров с разными статусами и разрешениями."""
    return [
        Donor.objects.create(
            email=faker.unique.email(),
            subscription=subscription,
            email_marketing_consent=consent,
        )
        for consent in (True, False)
        for subscription in (
            SubscriptionStatuses.ACTIVE.capitalized,
            SubscriptionStatuses.INACTIVE.capitalized,
        )
    ]


@pytest.mark.parametrize(
    "selection",
    ["all", "selected", "blocked", "empty", "missing"],
)
def test_get_donors_returns_use_case_data(
    donors: list[Donor],
    selection: str,
) -> None:
    """Полная и адресная выборки возвращают только разрешённые контакты."""
    allowed = [donor for donor in donors if donor.email_marketing_consent]
    blocked = [donor for donor in donors if not donor.email_marketing_consent]

    if selection == "all":
        donor_ids = None
        expected_donors = allowed
    elif selection == "selected":
        donor_ids = [allowed[0].pk, blocked[0].pk]
        expected_donors = allowed[:1]
    elif selection == "blocked":
        donor_ids = [donor.pk for donor in blocked]
        expected_donors = []
    elif selection == "empty":
        donor_ids = []
        expected_donors = []
    else:
        donor_ids = [max(donor.pk for donor in donors) + 1]
        expected_donors = []

    actual = list(
        DonorRepository().get_donors(donor_ids=donor_ids),
    )

    assert sorted(actual) == sorted(
        (donor.email, donor.subscription) for donor in expected_donors
    )
