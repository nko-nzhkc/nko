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

COMPLETED_PAYMENT_STATUS = "Completed"


pytestmark = pytest.mark.usefixtures(
    "sync_task",
    "email_task",
    "chain_factory",
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "subscription_case",
    [
        (SubscriptionStatuses.ACTIVE.capitalized, True),
        (SubscriptionStatuses.INACTIVE.capitalized, False),
    ],
    ids=["active", "inactive"],
)
def test_new_donor_uses_payment_subscription(
    faker: Faker,
    django_capture_on_commit_callbacks: Any,
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
    *,
    subscription_case: tuple[str, bool],
) -> None:
    """Новый донор создаётся с переданным статусом подписки."""
    subscription, sends_email = subscription_case
    email = faker.unique.email()

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            donor_email=email,
            payment_status=COMPLETED_PAYMENT_STATUS,
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
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
) -> None:
    """Новый донор не создаётся сразу со статусом Lost."""
    email = faker.unique.email()

    create_or_update_donor(
        donor_email=email,
        payment_status=COMPLETED_PAYMENT_STATUS,
        subscription=SubscriptionStatuses.LOST.capitalized,
    )

    assert not Donor.objects.filter(email=email).exists()
    sync_task.si.assert_not_called()
    email_task.si.assert_not_called()
    chain_factory.assert_not_called()


@pytest.mark.django_db
def test_failed_payment_counts_active_donor(
    make_donor: Callable[..., Donor],
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
def test_third_failure_marks_active_donor_lost(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Третий отказ переводит Active-донора в Lost."""
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
def test_failed_payment_keeps_inactive_donor(
    make_donor: Callable[..., Donor],
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
def test_successful_payment_reactivates_lost(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Успешный платёж активирует существующего Lost-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.LOST.capitalized,
        count_declined=2,
    )

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=COMPLETED_PAYMENT_STATUS,
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
def test_successful_payment_resets_active_count(
    make_donor: Callable[..., Donor],
) -> None:
    """Успешный платёж сбрасывает счётчик Active-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status=COMPLETED_PAYMENT_STATUS,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0


@pytest.mark.django_db
def test_successful_payment_resets_inactive_count(
    make_donor: Callable[..., Donor],
) -> None:
    """Успешный платёж сбрасывает счётчик Inactive-донора."""
    donor = make_donor(
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        donor_email=donor.email,
        payment_status=COMPLETED_PAYMENT_STATUS,
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.INACTIVE.capitalized
    assert donor.count_declined == 0
