"""Модуль бизнес логики доноров."""

import logging
from functools import partial

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


def donor_exists(email):
    """Метод проверки наличия контакта донора в ДБ."""
    return Donor.objects.filter(email=email).exists()


def ad_donor(
    donor,
    subscription,
    update,
    *,
    send_email=False,
):
    """Сохраняет донора и планирует импорт, затем при необходимости письмо."""
    with transaction.atomic():
        donor_obj, _ = Donor.objects.update_or_create(
            email=donor,
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


def _handle_failed_payment(data, donor):
    """Обрабатывает случай неуспешного платежа для существующего донора."""
    if donor.subscription == SubscriptionStatuses.ACTIVE.capitalized:
        # если у донора 3й отклонённый платёж
        if donor.count_declined + 1 == BAD_PAYMENTS_COUNT:
            ad_donor(
                data["email"],
                SubscriptionStatuses.LOST.capitalized,
                update=True,
            )
            logger.info(
                "У Донора %s обновлен статус на %s",
                {data["email"]},
                SubscriptionStatuses.LOST.capitalized,
            )
        else:
            Donor.objects.filter(email=data["email"]).update(
                count_declined=FExpression("count_declined") + 1,
            )


def _handle_active_subscription(data, donor):
    """Обрабатывает случай успешного платежа с активной подпиской."""
    # если старый статус "Lost", "Inactive"
    if donor.subscription in NEGATIVE_SUB_STAT:
        ad_donor(
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
            update=True,
            send_email=True,
        )
        logger.info(
            "У Донора %s обновлен статус на %s",
            {data["email"]},
            SubscriptionStatuses.ACTIVE.capitalized,
        )
    else:
        Donor.objects.filter(email=data["email"]).update(
            count_declined=0,
        )


def _create_new_donor(data, subscription):
    """Создает нового донора в зависимости от статуса подписки."""
    if subscription == SubscriptionStatuses.INACTIVE.capitalized:
        ad_donor(
            data["email"],
            SubscriptionStatuses.INACTIVE.capitalized,
            update=False,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            data["email"],
            SubscriptionStatuses.INACTIVE.capitalized,
        )
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        ad_donor(
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
            update=False,
            send_email=True,
        )
        logger.info(
            "Создан Донор %s со статусом %s",
            data["email"],
            SubscriptionStatuses.ACTIVE.capitalized,
        )


def _update_existing_donor(data, subscription):
    """Обновляет статус существующего донора в зависимости от платежа."""
    donor = Donor.objects.get(email=data["email"])
    if data["status"] in FailedPaymentStatuses:
        _handle_failed_payment(data, donor)
    elif subscription == SubscriptionStatuses.ACTIVE.capitalized:
        _handle_active_subscription(data, donor)
    else:
        Donor.objects.filter(email=data["email"]).update(
            count_declined=0,
        )


def create_or_update_donor(data, subscription):
    """Создаем нового донора или обновляем статус существующего."""
    if donor_exists(data["email"]):
        _update_existing_donor(data, subscription)
    else:
        _create_new_donor(data, subscription)