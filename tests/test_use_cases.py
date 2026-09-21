"""Тесты сценариев API."""

from unittest.mock import patch

import pytest

from api.repositories import DonorRepository
from api.use_cases import (
    UNISENDER_BATCH_SIZE,
    UNISENDER_FIELD_NAMES,
    SyncDonorsToUnisenderUseCase,
)
from contacts.models import Donor
from donor_base import di
from donor_base.constants import SubscriptionStatuses
from donor_base.subscriptions import get_group_by_capitalized


@pytest.fixture
def donor_factory(db, faker):
    """Создаёт реальные записи доноров для сценария."""

    def create(count):
        subscription = SubscriptionStatuses.ACTIVE.capitalized
        return Donor.objects.bulk_create([
            Donor(
                email=faker.unique.email(),
                subscription=subscription,
            )
            for _ in range(count)
        ])

    return create


@pytest.fixture
def api_request():
    """Изолирует отправку запроса во внешний Unisender."""
    with patch(
        "donor_base.unisender_client.Client._api_request"
    ) as request:
        yield request


@pytest.fixture
def use_case(api_request):
    """Создаёт сценарий с реальными production-зависимостями."""
    return SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )


def test_execute_sends_exactly_one_batch_of_500_donors(
    donor_factory,
    use_case,
    api_request,
):
    """500 доноров отправляются одним вызовом importContacts."""
    donors = donor_factory(UNISENDER_BATCH_SIZE)

    use_case.execute()

    api_request.assert_called_once()
    method, payload = api_request.call_args.args

    assert method == "import_contacts"
    assert payload["field_names"] == UNISENDER_FIELD_NAMES
    assert payload["overwrite_lists"] == 1
    assert sorted(payload["data"]) == sorted(
        [
            donor.email,
            get_group_by_capitalized(donor.subscription),
        ]
        for donor in donors
    )


def test_execute_splits_501_donors_into_two_batches(
    donor_factory,
    use_case,
    api_request,
):
    """501 донор разделяется на пачки 500 и 1."""
    donors = donor_factory(UNISENDER_BATCH_SIZE + 1)

    use_case.execute()

    assert api_request.call_count == 2

    payloads = []
    for recorded_call in api_request.call_args_list:
        method, payload = recorded_call.args
        assert method == "import_contacts"
        assert payload["field_names"] == UNISENDER_FIELD_NAMES
        assert payload["overwrite_lists"] == 1
        payloads.append(payload)

    assert [len(payload["data"]) for payload in payloads] == [
        UNISENDER_BATCH_SIZE,
        1,
    ]

    actual = [
        row
        for payload in payloads
        for row in payload["data"]
    ]
    expected = [
        [donor.email, get_group_by_capitalized(donor.subscription)]
        for donor in donors
    ]

    assert sorted(actual) == sorted(expected)


@pytest.mark.parametrize("overwrite_lists", [0, 1])
def test_execute_passes_filter_and_overwrite_lists(
    overwrite_lists,
    donor_factory,
    use_case,
    api_request
):
    """Сценарий передаёт фильтр и сохраняет режим обновления."""
    donors = donor_factory(2)
    selected = donors[0]

    use_case.execute(
        donor_ids=[selected.pk],
        overwrite_lists=overwrite_lists,
    )

    api_request.assert_called_once_with(
        "import_contacts",
        {
            "field_names": UNISENDER_FIELD_NAMES,
            "data": [[
                selected.email,
                get_group_by_capitalized(selected.subscription),
            ]],
            "overwrite_lists": overwrite_lists,
        },
    )


def test_execute_does_not_send_empty_selection(
    donor_factory,
    use_case,
    api_request,
):
    """Пустая выборка не приводит к отправке контактов."""
    donor_factory(1)

    use_case.execute(donor_ids=[])

    api_request.assert_not_called()
