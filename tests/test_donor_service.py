"""Тесты переходов состояний донора."""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from faker import Faker

from api.donor_service import (
    create_or_update_donor,
    has_email_marketing_consent,
)
from contacts.models import Donor
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    FailedPaymentStatuses,
    SubscriptionStatuses,
)

COMPLETED_PAYMENT_STATUS = "Completed"
CONSENT_FIELD = "email_marketing_consent"


pytestmark = pytest.mark.usefixtures(
    "sync_task",
    "email_task",
    "chain_factory",
)


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({CONSENT_FIELD: True}, True),
        ('{"email_marketing_consent": true}', True),
        ({CONSENT_FIELD: False}, False),
        ({CONSENT_FIELD: "true"}, False),
        ({CONSENT_FIELD: 1}, False),
        ({}, False),
        (None, False),
        ("invalid json", False),
        ("[]", False),
    ],
    ids=[
        "object-true",
        "json-true",
        "false",
        "string-is-not-consent",
        "number-is-not-consent",
        "missing-key",
        "no-metadata",
        "invalid-json",
        "json-is-not-object",
    ],
)
def test_consent_requires_explicit_json_true(
    metadata: object,
    *,
    expected: bool,
) -> None:
    """Только явный boolean true разрешает передачу в Unisender."""
    assert has_email_marketing_consent(metadata) is expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "subscription_case",
    [
        (SubscriptionStatuses.ACTIVE.capitalized, True, False),
        (SubscriptionStatuses.INACTIVE.capitalized, False, False),
        (SubscriptionStatuses.ACTIVE.capitalized, True, True),
        (SubscriptionStatuses.INACTIVE.capitalized, False, True),
    ],
    ids=[
        "active-without-consent",
        "inactive-without-consent",
        "active-with-consent",
        "inactive-with-consent",
    ],
)
def test_new_donor_uses_payment_subscription(
    faker: Faker,
    django_capture_on_commit_callbacks: Any,
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
    *,
    subscription_case: tuple[str, bool, bool],
) -> None:
    """Донор сохраняется всегда, workflow создаётся только с согласием."""
    subscription = subscription_case[0]
    email = faker.unique.email()

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        create_or_update_donor(
            donor_email=email,
            payment_status=COMPLETED_PAYMENT_STATUS,
            subscription=subscription,
            email_marketing_consent=subscription_case[2],
        )

    donor = Donor.objects.get(email=email)
    assert Donor.objects.filter(email=email).count() == 1
    assert donor.subscription == subscription
    assert donor.count_declined == 0
    assert donor.email_marketing_consent is subscription_case[2]
    assert len(callbacks) == int(subscription_case[2])

    if not subscription_case[2]:
        for signature_factory in (
            sync_task.si,
            email_task.si,
            chain_factory,
        ):
            signature_factory.assert_not_called()
        return

    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=0,
    )

    if subscription_case[1]:
        email_task.si.assert_called_once_with(
            email=email,
            list_id="5",
        )
        chain_factory.assert_called_once()
        chain_factory.return_value.apply_async.assert_called_once()
    else:
        for signature_factory in (email_task.si, chain_factory):
            signature_factory.assert_not_called()
        sync_task.si.return_value.apply_async.assert_called_once()


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
@pytest.mark.parametrize("initial_consent", [False, True])
def test_third_failure_marks_active_donor_lost(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    django_capture_on_commit_callbacks: Any,
    *,
    initial_consent: bool,
) -> None:
    """Переход в Lost ставит один импорт, включая первое согласие."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=BAD_PAYMENTS_COUNT - 1,
        email_marketing_consent=initial_consent,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=FailedPaymentStatuses.DECLINED.value,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
            email_marketing_consent=not initial_consent,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.LOST.capitalized
    assert donor.count_declined == 0
    assert donor.email_marketing_consent is True
    assert len(callbacks) == 1
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    sync_task.si.return_value.apply_async.assert_called_once()


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
@pytest.mark.parametrize("initial_consent", [False, True])
def test_successful_payment_reactivates_lost(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
    django_capture_on_commit_callbacks: Any,
    *,
    initial_consent: bool,
) -> None:
    """Реактивация ставит один workflow, включая первое согласие."""
    donor = make_donor(
        subscription=SubscriptionStatuses.LOST.capitalized,
        count_declined=2,
        email_marketing_consent=initial_consent,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=COMPLETED_PAYMENT_STATUS,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
            email_marketing_consent=not initial_consent,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0
    assert donor.email_marketing_consent is True
    assert len(callbacks) == 1
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    email_task.si.assert_called_once_with(
        email=donor.email,
        list_id="5",
    )
    chain_factory.assert_called_once()
    chain_factory.return_value.apply_async.assert_called_once()


@pytest.mark.django_db
@pytest.mark.parametrize("consent", [False, True])
def test_successful_payment_resets_active_count(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    email_task: MagicMock,
    django_capture_on_commit_callbacks: Any,
    *,
    consent: bool,
) -> None:
    """Повторный платёж сбрасывает счётчик, но не меняет согласие."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=2,
        email_marketing_consent=consent,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=COMPLETED_PAYMENT_STATUS,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0
    assert donor.email_marketing_consent is consent
    assert not callbacks
    sync_task.si.assert_not_called()
    email_task.si.assert_not_called()


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


@pytest.mark.django_db
def test_first_consent_schedules_one_import(
    make_donor: Callable[..., Donor],
    sync_task: MagicMock,
    email_task: MagicMock,
    chain_factory: MagicMock,
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Первое согласие синхронизирует донора; повторное не дублирует задачу."""
    donor = make_donor(
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        email_marketing_consent=False,
    )

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=COMPLETED_PAYMENT_STATUS,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
            email_marketing_consent=True,
        )

    donor.refresh_from_db()
    assert donor.email_marketing_consent is True
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert len(callbacks) == 1
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    sync_task.si.return_value.apply_async.assert_called_once()

    with django_capture_on_commit_callbacks(execute=True) as repeated:
        create_or_update_donor(
            donor_email=donor.email,
            payment_status=COMPLETED_PAYMENT_STATUS,
            subscription=SubscriptionStatuses.ACTIVE.capitalized,
            email_marketing_consent=True,
        )

    assert not repeated
    for operation in (
        sync_task.si,
        sync_task.si.return_value.apply_async,
    ):
        operation.assert_called_once()
    email_task.si.assert_not_called()
    chain_factory.assert_not_called()
