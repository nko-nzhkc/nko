"""Модуль бизнес логики доноров."""

import logging
from functools import partial
from typing import TypedDict

from celery import chain
from contacts.models import Donor
from django.db import transaction
from django.db.models import F as FExpression
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    NEGATIVE_SUB_STAT,
    FailedPaymentStatuses,
    SubscriptionStatuses,
)
from donor_base.subscriptions import get_group_by_capitalized

from api.tasks import (
    send_payment_email_task,
    send_users_to_unisender,
)

logger = logging.getLogger(__name__)


class DonorPayload(TypedDict):
    """Минимальные данные донора, используемые сервисом."""

    email: str
    status: str


def ad_donor(
    donor_email: str,
    subscription: str,
    update: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
    *,
    send_email: bool = False,
) -> None:
    """Сохраняет донора и планирует импорт, затем при необходимости письмо."""
    donor_obj, _ = Donor.objects.update_or_create(
        email=donor_email,
        defaults={
            "subscription": subscription,
            "count_declined": 0,
        },
    )

    workflow = send_users_to_unisender.si(
        donor_ids=[donor_obj.pk],
        overwrite_lists=1 if update else 0,
    )

    if send_email:
        workflow = chain(
            workflow,
            send_payment_email_task.si(
                email=donor_obj.email,
                list_id=get_group_by_capitalized(subscription),
            ),
        )

    transaction.on_commit(
        partial(workflow.apply_async),
    )


def _handle_failed_payment(donor_email: str, donor: Donor) -> None:
    """Обрабатывает случай неуспешного платежа для существующего донора."""
    if donor.subscription == SubscriptionStatuses.ACTIVE.capitalized:
        # если у донора 3й отклонённый платёж
        if donor.count_declined + 1 == BAD_PAYMENTS_COUNT:
            ad_donor(
                donor_email,
                SubscriptionStatuses.LOST.capitalized,
                update=True,
            )
            logger.info(
                "У Донора %s обновлен статус на %s",
                donor_email,
                SubscriptionStatuses.LOST.capitalized,
            )
        else:
            Donor.objects.filter(email=donor_email).update(
                count_declined=FExpression("count_declined") + 1,
            )


def _handle_active_subscription(donor_email: str, donor: Donor) -> None:
    """Обрабатывает случай успешного платежа с активной подпиской."""
    # если старый статус "Lost", "Inactive"
    if donor.subscription in NEGATIVE_SUB_STAT:
        ad_donor(
            donor_email,
            SubscriptionStatuses.ACTIVE.capitalized,
            update=True,
            send_email=True,
        )
        logger.info(
            "У Донора %s обновлен статус на %s",
            donor_email,
            SubscriptionStatuses.ACTIVE.capitalized,
        )
    else:
        Donor.objects.filter(email=donor_email).update(
            count_declined=0,
        )


def _create_new_donor(donor_email: str, subscription: str) -> None:
    """Создает нового донора в зависимости от статуса подписки."""
    if subscription == SubscriptionStatuses.INACTIVE.capitalized:
        ad_donor(
            donor_email,
            SubscriptionStatuses.INACTIVE.capitalized,
            update=False,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            donor_email,
            SubscriptionStatuses.INACTIVE.capitalized,
        )
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        ad_donor(
            donor_email,
            SubscriptionStatuses.ACTIVE.capitalized,
            update=False,
            send_email=True,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            donor_email,
            SubscriptionStatuses.ACTIVE.capitalized,
        )


def _update_existing_donor(
    donor_email: str,
    payment_status: str,
    subscription: str,
) -> None:
    """Обновляет статус существующего донора в зависимости от платежа."""
    donor = Donor.objects.get(email=donor_email)
    if payment_status in FailedPaymentStatuses:
        _handle_failed_payment(donor_email, donor)
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        _handle_active_subscription(donor_email, donor)
    else:
        Donor.objects.filter(email=donor_email).update(
            count_declined=0,
        )


def create_or_update_donor(data: DonorPayload, subscription: str) -> None:
    """Создаем нового донора или обновляем статус существующего."""
    donor_email = data["email"]
    payment_status = data["status"]
    if Donor.objects.filter(email=donor_email).exists():
        _update_existing_donor(donor_email, payment_status, subscription)
    else:
        _create_new_donor(donor_email, subscription)
