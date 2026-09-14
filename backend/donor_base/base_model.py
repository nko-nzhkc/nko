# Модуль базовой модели для всех пожертвований.
from django.db import models

from api.validators import forbidden_words_validator

from donor_base.constants import (
    PAYMENT_METHOD_LENGTH, ZERO, MAX_EMAIL_LENGTH,
    MAX_CURRENCY_LENGTH, MAX_PAYMENT_OPERATOR_LENGTH,
    MAX_PAYMENT_ID_LENGTH, MAX_PAYMENT_STATUS_LENGTH
)


class BaseModelDonation(models.Model):
    """Базовая модель для всех пожертвований."""

    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        validators=[forbidden_words_validator],
        verbose_name="Электронная почта",
    )
    donat = models.PositiveSmallIntegerField(
        # choices=settings.AMOUNT,
        default=ZERO,
        verbose_name="Размер пожертвования",
    )
    custom_donat = models.PositiveIntegerField(
        default=ZERO,
        verbose_name="Кастомизированный размер пожертвования",
    )
    payment_method = models.CharField(
        max_length=PAYMENT_METHOD_LENGTH,
        verbose_name="Способ оплаты",
    )
    monthly_donat = models.BooleanField(
        default=False,
        verbose_name="Чекбокс о ежемесячном пожертвовании",
    )
    subscription = models.BooleanField(
        default=False,
        verbose_name="Чекбокс об отмене подписки",
    )
    pub_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата публикации пожертвования",
    )
    payment_id = models.CharField(
        max_length=MAX_PAYMENT_ID_LENGTH,
        verbose_name="Идентификатор платежа",
    )
    status = models.CharField(
        max_length=MAX_PAYMENT_STATUS_LENGTH,
        verbose_name="Статус платежа",
    )
    user_account_id = models.PositiveIntegerField(
        verbose_name="Идентификатор пользователя",
    )
    date_created = models.DateTimeField(
        verbose_name="Дата создания платежа",
    )
    date_processed = models.DateTimeField(
        verbose_name="Дата обработки платежа",
    )
    payment_operator = models.CharField(
        max_length=MAX_PAYMENT_OPERATOR_LENGTH,
        verbose_name="Платежный оператор",
    )
    currency = models.CharField(
        max_length=MAX_CURRENCY_LENGTH,
        verbose_name="Валюта платежа"
    )

    class Meta:
        abstract = True
