"""Тесты сценариев API."""

from functools import partial
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

IMPORT_CONTACTS_METHOD = "import_contacts"
FIELD_NAMES_KEY = "field_names"
DATA_KEY = "data"
OVERWRITE_LISTS_KEY = "overwrite_lists"


def _create_donors(faker, count):
    """Создаёт count реальных доноров с активной подпиской."""
    subscription = SubscriptionStatuses.ACTIVE.capitalized
    return Donor.objects.bulk_create([
        Donor(email=faker.unique.email(), subscription=subscription)
        for _ in range(count)
    ])


@pytest.fixture
def donor_factory(db, faker):
    """Создаёт реальные записи доноров для сценария."""
    return partial(_create_donors, faker)


@pytest.fixture
def api_request():
    """Изолирует отправку запроса во внешний Unisender."""
    with patch(
        "donor_base.unisender_client.Client._api_request",
    ) as request:
        yield request


@pytest.fixture
def use_case(api_request):
    """Создаёт сценарий с реальными production-зависимостями."""
    return SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )


def _donor_row(donor):
    """Преобразует донора в строку payload для Unisender."""
    return [donor.email, get_group_by_capitalized(donor.subscription)]


def _assert_common_payload_shape(payload):
    """Проверяет общие для всех пачек поля payload."""
    assert payload[FIELD_NAMES_KEY] == UNISENDER_FIELD_NAMES


def _assert_batch_payload(payload):
    """Проверяет форму и режим перезаписи для одной пачки."""
    _assert_common_payload_shape(payload)
    assert payload[OVERWRITE_LISTS_KEY] == 1


def _assert_batches_payloads(payloads):
    """Проверяет форму и режим перезаписи для всех пачек."""
    for payload in payloads:
        _assert_batch_payload(payload)


def test_execute_sends_batch_for_full_size(
    donor_factory,
    use_case,
    api_request,
):
    """Полная пачка доноров отправляется одним вызовом importContacts."""
    donors = donor_factory(UNISENDER_BATCH_SIZE)

    use_case.execute()

    api_request.assert_called_once()
    method, payload = api_request.call_args.args

    assert method == IMPORT_CONTACTS_METHOD
    _assert_batch_payload(payload)
    assert sorted(payload[DATA_KEY]) == sorted(
        _donor_row(donor) for donor in donors
    )


def test_execute_splits_overflow_into_two_batches(
    donor_factory,
    use_case,
    api_request,
):
    """Пачка сверх лимита разделяется на полную и остаточную части."""
    donors = donor_factory(UNISENDER_BATCH_SIZE + 1)

    use_case.execute()

    assert api_request.call_count == 2

    calls = api_request.call_args_list
    payloads = [recorded_call.args[1] for recorded_call in calls]

    assert {recorded_call.args[0] for recorded_call in calls} == {
        IMPORT_CONTACTS_METHOD,
    }
    _assert_batches_payloads(payloads)

    assert [len(payload[DATA_KEY]) for payload in payloads] == [
        UNISENDER_BATCH_SIZE,
        1,
    ]

    actual = [row for payload in payloads for row in payload[DATA_KEY]]
    expected = [_donor_row(donor) for donor in donors]

    assert sorted(actual) == sorted(expected)


@pytest.mark.parametrize("overwrite_lists", [0, 1])
def test_execute_passes_filter_and_overwrite_mode(
    overwrite_lists,
    donor_factory,
    use_case,
    api_request,
):
    """Сценарий передаёт фильтр и сохраняет режим обновления."""
    donors = donor_factory(2)
    selected = donors[0]

    use_case.execute(
        donor_ids=[selected.pk],
        overwrite_lists=overwrite_lists,
    )

    api_request.assert_called_once_with(
        IMPORT_CONTACTS_METHOD,
        {
            FIELD_NAMES_KEY: UNISENDER_FIELD_NAMES,
            DATA_KEY: [_donor_row(selected)],
            OVERWRITE_LISTS_KEY: overwrite_lists,
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
