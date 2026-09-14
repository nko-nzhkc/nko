# Модуль модели контактов.
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from api.validators import forbidden_words_validator

from donor_base.constants import (
    ZERO, MAX_USERNAME_LENGTH, MAX_EMAIL_LENGTH,
    MAX_SUBJECT_LENGTH, Subscriptions
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
        max_length=MAX_SUBJECT_LENGTH, verbose_name="Тема письма"
    )
    comment = models.TextField(verbose_name="Комментарий")

    class Meta:
        verbose_name = "Контакт"
        verbose_name_plural = "Контакты"
        constraints = [
            models.UniqueConstraint(
                fields=["username", "email"],
                name="Уникальное имя пользователя и электронная почта",
            )
        ]

    def __str__(self):
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
        choices=[(status.name, status.value) for status in Subscriptions],
        verbose_name="Статус подписки у донора",
    )
    count_declined = models.PositiveSmallIntegerField(
        default=ZERO,
        verbose_name="Счётчик неудачных платежей",
    )

    class Meta:
        verbose_name = "Донор"
        verbose_name_plural = "Доноры"

    def __str__(self):
        return self.email
