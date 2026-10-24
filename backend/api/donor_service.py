"""Модуль бизнес логики доноров."""

import json
import logging
from functools import partial

from celery import chain
from django.db import transaction
from django.db.models import F as FExpression

from api.tasks import (
    send_payment_email_task,
    send_users_to_unisender,
)
from contacts.models import Donor
from donor_base.constants import (
    BAD_PAYMENTS_COUNT,
    NEGATIVE_SUB_STAT,
    FailedPaymentStatuses,
    SubscriptionStatuses,
)
from donor_base.subscriptions import get_group_by_capitalized

logger = logging.getLogger(__name__)


def has_email_marketing_consent(metadata: object) -> bool:
    """Проверяет явное согласие в дополнительных данных платежа."""
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return False

    if not isinstance(metadata, dict):
        return False

    return metadata.get("email_marketing_consent") is True


def ad_donor(
    donor_email: str,
    subscription: str,
    update: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
    *,
    send_email: bool = False,
    email_marketing_consent: bool = False,
) -> None:
    """Сохраняет донора и планирует импорт, затем при необходимости письмо."""
    donor_obj, _ = Donor.objects.update_or_create(
        email=donor_email,
        defaults={
            "subscription": subscription,
            "count_declined": 0,
        },
        create_defaults={
            "subscription": subscription,
            "count_declined": 0,
            "email_marketing_consent": email_marketing_consent is True,
        },
    )

    if not donor_obj.email_marketing_consent:
        return

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


def _create_new_donor(
    donor_email: str,
    subscription: str,
    *,
    email_marketing_consent: bool = False,
) -> None:
    """Создает нового донора в зависимости от статуса подписки."""
    if subscription == SubscriptionStatuses.INACTIVE.capitalized:
        ad_donor(
            donor_email,
            SubscriptionStatuses.INACTIVE.capitalized,
            update=False,
            email_marketing_consent=email_marketing_consent,
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
            email_marketing_consent=email_marketing_consent,
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


@transaction.atomic
def create_or_update_donor(
    donor_email: str,
    payment_status: str,
    subscription: str,
    *,
    email_marketing_consent: bool = False,
) -> None:
    """Создаем нового донора или обновляем статус существующего."""
    donor = Donor.objects.select_for_update().filter(email=donor_email).first()
    if donor is None:
        _create_new_donor(
            donor_email,
            subscription,
            email_marketing_consent=email_marketing_consent,
        )
        return

    consent_granted = (
        email_marketing_consent is True and not donor.email_marketing_consent
    )
    if consent_granted:
        donor.email_marketing_consent = True
        donor.save(update_fields=["email_marketing_consent"])

    previous_subscription = donor.subscription
    _update_existing_donor(donor_email, payment_status, subscription)

    if consent_granted:
        donor.refresh_from_db(fields=["subscription"])
        if donor.subscription == previous_subscription:
            workflow = send_users_to_unisender.si(
                donor_ids=[donor.pk],
                overwrite_lists=1,
            )
            transaction.on_commit(
                partial(workflow.apply_async),
            )
