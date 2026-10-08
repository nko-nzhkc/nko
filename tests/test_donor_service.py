"""Тесты переходов состояний донора."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from faker import Faker

from api.donor_service import create_or_update_donor
from contacts.models import Donor
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    FailedPaymentStatuses,
    SubscriptionStatuses,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("subscription", "sends_email"),
    [
        (SubscriptionStatuses.ACTIVE.capitalized, True),
        (SubscriptionStatuses.INACTIVE.capitalized, False),
    ],
)
def test_new_donor_is_created_with_payment_subscription(
    subscription: str,
    *,
    sends_email: bool,
    faker: Faker,
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Новый донор создаётся с переданным статусом подписки."""
    sync_task, email_task, chain_factory = donor_workflow
    email = faker.unique.email()

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            donor_email=email,
            payment_status="Completed",
            subscription=subscription,
        )

    donor = Donor.objects.get(email=email)
    assert donor.subscription == subscription
    assert donor.count_declined == 0
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=0,
    )

    if sends_email:
        email_task.si.assert_called_once_with(
            email=email,
            list_id="5",
        )
        chain_factory.assert_called_once()
    else:
        email_task.si.assert_not_called()
        chain_factory.assert_not_called()


@pytest.mark.django_db
def test_new_lost_donor_is_not_created(
    faker: Faker,
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Новый донор не создаётся сразу со статусом Lost."""
    sync_task, email_task, chain_factory = donor_workflow
    email = faker.unique.email()

    create_or_update_donor(
        donor_email=email,
        payment_status="Completed",
        subscription=SubscriptionStatuses.LOST.capitalized,
    )

    assert not Donor.objects.filter(email=email).exists()
    sync_task.si.assert_not_called()
    email_task.si.assert_not_called()
    chain_factory.assert_not_called()


@pytest.mark.django_db
def test_failed_payment_increments_active_donor_count(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Неудачный платёж до порога увеличивает счётчик отказов."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=1,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status=FailedPaymentStatuses.FAILURE.value,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 2


@pytest.mark.django_db
def test_third_failed_payment_marks_active_donor_lost(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Третий отказ переводит Active-донора в Lost."""
    sync_task, _, _ = donor_workflow
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=BAD_PAYMENTS_COUNT - 1,
    )

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=FailedPaymentStatuses.DECLINED.value,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.LOST.capitalized
    assert donor.count_declined == 0
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )


@pytest.mark.django_db
def test_failed_payment_does_not_change_inactive_donor(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Отказ платежа не меняет счётчик Inactive-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
        count_declined=1,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status=FailedPaymentStatuses.CANCELLED.value,
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.INACTIVE.capitalized
    assert donor.count_declined == 1


@pytest.mark.django_db
def test_successful_payment_reactivates_lost_donor(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Успешный платёж активирует существующего Lost-донора."""
    sync_task, email_task, chain_factory = donor_workflow
    donor = make_donor(
        subscription=SubscriptionStatuses.LOST.capitalized,
        count_declined=2,
    )

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            donor_email=donor.email,
            payment_status="Completed",
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    email_task.si.assert_called_once_with(
        email=donor.email,
        list_id="5",
    )
    chain_factory.assert_called_once()


@pytest.mark.django_db
def test_successful_payment_resets_active_donor_count(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Успешный платёж сбрасывает счётчик Active-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status="Completed",
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0


@pytest.mark.django_db
def test_successful_payment_resets_inactive_donor_count(
    make_donor: Callable[..., Donor],
    donor_workflow: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Успешный платёж сбрасывает счётчик Inactive-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status="Completed",
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.INACTIVE.capitalized
    assert donor.count_declined == 0
