# Модуль модели платежа Mixplat.
from django.conf import settings
from django.db import models

from donations.models import Donation


class MixPlat(Donation):
    """Модель платежа Mixplat."""

    payment_id = models.CharField(
        max_length=settings.MAX_PAYMENT_ID_LENGTH,
        verbose_name="ID платежа",
    )
    status = models.CharField(
        max_length=settings.MAX_PAYMENT_STATUS_LENGTH,
        verbose_name="Статус платежа",
    )
    user_account_id = models.PositiveIntegerField(
        verbose_name="ID пользователя в Mixplat",
    )
    user_comment = models.CharField(
        max_length=settings.MAX_USER_COMMENT_LENGTH,
        verbose_name="Номер и дата договора",
    )
    date_created = models.DateTimeField(
        verbose_name="Дата создания платежа",
    )
    date_processed = models.DateTimeField(
        verbose_name="Дата проведения платежа",
    )

    class Meta:
        ordering = ("-pub_date",)
        verbose_name = "Платеж Mixplat"
        verbose_name_plural = "Платежы Mixplat"
