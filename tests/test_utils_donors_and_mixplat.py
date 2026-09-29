"""Тесты donor-flow и webhook Mixplat из api.utils."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from api.utils import (
    create_or_update_donor,
    donor_exists,
    mixplat_request_handler,
    string_to_date,
)
from contacts.models import Donor
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    DATE_FORMAT,
    PaymentStatuses,
    SubscriptionStatuses,
)
from donor_base.subscriptions import get_group_by_capitalized
from mixplat.models import MixPlat


@pytest.fixture
def payment_data(faker):
    """Минимальный набор данных платежа для create_or_update_donor."""
    return {
        "email": faker.unique.email(),
        "status": "Completed",
    }


@pytest.fixture
def workflow_mocks():
    """Изолирует публикацию Celery workflow при обновлении доноров."""
    with (
        patch("api.utils.send_users_to_unisender") as sync_task,
        patch("api.utils.send_payment_email_task") as email_task,
        patch("api.utils.chain") as chain_factory,
    ):
        yield sync_task, email_task, chain_factory


def assert_donor(email, subscription, count_declined=0):
    """Проверяет сохранённое состояние донора."""
    donor = Donor.objects.get(email=email)
    assert donor.subscription == subscription
    assert donor.count_declined == count_declined
    return donor


def mixplat_payload(email, recurrent_id=None):
    """Формирует payload webhook Mixplat."""
    payload = {
        "user_email": email,
        "amount": 100,
        "amount_user": 150,
        "payment_method": "card",
        "payment_id": "payment-1",
        "status": "success",
        "user_account_id": 42,
        "date_created": "2024-01-02 03:04:05",
        "date_processed": "2024-01-02 03:05:05",
        "currency": "RUB",
    }
    if recurrent_id is not None:
        payload["recurrent_id"] = recurrent_id
    return payload


def test_string_to_date_returns_aware_datetime():
    """Строковая дата преобразуется в timezone-aware datetime."""
    value = "2024-01-02 03:04:05"

    result = string_to_date(value)

    assert timezone.is_aware(result)
    assert result.strftime(DATE_FORMAT) == value


@pytest.mark.django_db
def test_donor_exists_returns_both_boolean_values(faker):
    """Проверка наличия донора возвращает False и True
    в зависимости от БД.
    """
    email = faker.unique.email()

    assert donor_exists(email) is False
    Donor.objects.create(
        email=email,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )

    assert donor_exists(email) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "subscription, sends_email",
    [
        (SubscriptionStatuses.INACTIVE.capitalized, False),
        (SubscriptionStatuses.ACTIVE.capitalized, True),
    ],
)
def test_create_or_update_donor_creates_new_donor(
    payment_data,
    subscription,
    sends_email,
    workflow_mocks,
    django_capture_on_commit_callbacks,
):
    """Новый донор создаётся как Active или Inactive
    согласно платежной системе.
    """
    sync_task, email_task, chain_factory = workflow_mocks

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(payment_data, subscription)

    donor = assert_donor(payment_data["email"], subscription)
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=0,
    )
    if sends_email:
        email_task.si.assert_called_once_with(
            email=payment_data["email"],
            list_id=get_group_by_capitalized(subscription),
        )
        chain_factory.assert_called_once()
    else:
        email_task.si.assert_not_called()
        chain_factory.assert_not_called()


@pytest.mark.django_db
def test_create_or_update_donor_does_not_create_new_lost_donor(
    payment_data,
    workflow_mocks,
):
    """Новый донор со статусом Lost не создаётся до появления в базе."""
    sync_task, email_task, chain_factory = workflow_mocks

    create_or_update_donor(
        payment_data,
        SubscriptionStatuses.LOST.capitalized,
    )

    assert not Donor.objects.filter(email=payment_data["email"]).exists()
    sync_task.si.assert_not_called()
    email_task.si.assert_not_called()
    chain_factory.assert_not_called()


@pytest.mark.django_db
def test_create_or_update_donor_marks_active_donor_as_lost_after_third_decline(
    payment_data,
    workflow_mocks,
    django_capture_on_commit_callbacks,
):
    """Третий неуспешный платёж активного донора переводит его в Lost."""
    sync_task, _, _ = workflow_mocks
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=BAD_PAYMENTS_COUNT - 1,
    )
    payment_data["status"] = PaymentStatuses.DECLINED

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            payment_data,
            SubscriptionStatuses.ACTIVE.capitalized,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.LOST.capitalized
    assert donor.count_declined == 0
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )


@pytest.mark.django_db
def test_create_or_update_donor_increments_active_donor_declines(payment_data):
    """Неуспешный платёж до третьего подряд только увеличивает счётчик."""
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=1,
    )
    payment_data["status"] = PaymentStatuses.FAILURE

    create_or_update_donor(
        payment_data, SubscriptionStatuses.ACTIVE.capitalized
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 2


@pytest.mark.django_db
def test_create_or_update_donor_ignores_failed_payment_for_inactive_donor(
    payment_data,
):
    """Неуспешный платёж не меняет счётчик неактивного донора."""
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
        count_declined=1,
    )
    payment_data["status"] = PaymentStatuses.CANCELLED

    create_or_update_donor(
        payment_data, SubscriptionStatuses.INACTIVE.capitalized
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.INACTIVE.capitalized
    assert donor.count_declined == 1


@pytest.mark.django_db
def test_create_or_update_donor_reactivates_lost_donor_after_success(
    payment_data,
    workflow_mocks,
    django_capture_on_commit_callbacks,
):
    """Успешный платёж с активной подпиской реактивирует Lost-донора."""
    sync_task, email_task, chain_factory = workflow_mocks
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.LOST.capitalized,
        count_declined=2,
    )

    with django_capture_on_commit_callbacks(execute=True):
        create_or_update_donor(
            payment_data,
            SubscriptionStatuses.ACTIVE.capitalized,
        )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0
    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    email_task.si.assert_called_once_with(
        email=payment_data["email"],
        list_id=SubscriptionStatuses.ACTIVE.group_id,
    )
    chain_factory.assert_called_once()


@pytest.mark.django_db
def test_create_or_update_donor_resets_active_donor_declines_after_success(
    payment_data,
):
    """Успешный платёж активного донора обнуляет счётчик отклонений."""
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        payment_data, SubscriptionStatuses.ACTIVE.capitalized
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.ACTIVE.capitalized
    assert donor.count_declined == 0


@pytest.mark.django_db
def test_create_or_update_donor_resets_declines_for_inactive_subscription(
    payment_data,
):
    """Платёж без активной подписки тоже сбрасывает счётчик отклонений."""
    donor = Donor.objects.create(
        email=payment_data["email"],
        subscription=SubscriptionStatuses.INACTIVE.capitalized,
        count_declined=2,
    )

    create_or_update_donor(
        payment_data, SubscriptionStatuses.INACTIVE.capitalized
    )

    donor.refresh_from_db()
    assert donor.subscription == SubscriptionStatuses.INACTIVE.capitalized
    assert donor.count_declined == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "recurrent_id, expected_subscription",
    [
        ("rec-1", SubscriptionStatuses.ACTIVE.capitalized),
        (None, SubscriptionStatuses.INACTIVE.capitalized),
    ],
)
def test_mixplat_request_handler_creates_payment_and_updates_donor(
    faker,
    recurrent_id,
    expected_subscription,
):
    """Webhook Mixplat сохраняет платёж и выбирает статус подписки."""
    email = faker.unique.email()
    request = SimpleNamespace(data=mixplat_payload(email, recurrent_id))

    with patch("api.utils.create_or_update_donor") as update_donor:
        response = mixplat_request_handler(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"result": "ok"}
    payment = MixPlat.objects.get(email=email)
    assert payment.donat == 100
    assert payment.custom_donat == 150
    assert payment.payment_operator == "mixplat"
    update_donor.assert_called_once()
    payment_data, subscription = update_donor.call_args.args
    assert payment_data["email"] == email
    assert subscription == expected_subscription


def test_mixplat_request_handler_returns_400_for_missing_required_key():
    """Webhook Mixplat возвращает 400 при неполном payload."""
    response = mixplat_request_handler(SimpleNamespace(data={}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {
        "result": "error",
        "error_description": "Internal error",
    }
