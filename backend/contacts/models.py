# Модуль модели контактов.
from typing import override

from api.validators import forbidden_words_validator
from django.contrib.auth.models import AbstractUser
from django.db import models
from donor_base.constants import (
    DEFAULT_DONATION,
    MAX_EMAIL_LENGTH,
    MAX_SUBJECT_LENGTH,
    MAX_USERNAME_LENGTH,
    SubscriptionStatuses,
)


class Contact(AbstractUser):
    """Модель контактов."""

    username = models.CharField(
        max_length=MAX_USERNAME_LENGTH,
        unique=True,
        validators=[forbidden_words_validator],
        verbose_name="Имя контакта",
    )
    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
        validators=[forbidden_words_validator],
        verbose_name="Электронная почта",
    )
    subject = models.CharField(
        max_length=MAX_SUBJECT_LENGTH,
        verbose_name="Тема письма",
    )
    comment = models.TextField(verbose_name="Комментарий")

    class Meta:
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"
        constraints = (
            models.UniqueConstraint(
                fields=["username", "email"],
                name="Уникальное имя пользователя и электронная почта",
            ),
        )

    @override
    def __str__(self) -> str:
        """Возвращает строковое представление контакта."""
        return f"{self.username} - {self.email}"


class Donor(models.Model):
    """Модель контактов доноров."""

    email = models.EmailField(
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
        validators=[forbidden_words_validator],
        verbose_name="Электронная почта донора",
    )
    subscription = models.TextField(
        choices=[
            (status.name, status.verbosed) for status in SubscriptionStatuses
        ],
        verbose_name="Статус подписки у донора",
    )
    count_declined = models.PositiveSmallIntegerField(
        default=DEFAULT_DONATION,
        verbose_name="Счётчик неудачных платежей",
    )

    class Meta:
        verbose_name = "Донор"
        verbose_name_plural = "Доноры"

    @override
    def __str__(self) -> str:
        """Строковое представление для модели Donor."""
        return self.email
