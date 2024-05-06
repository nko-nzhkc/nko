# Модуль модели контактов.
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from api.validators import forbidden_words_validator


class Contact(AbstractUser):
    """Модель контактов."""

    username = models.CharField(
        max_length=settings.MAX_USERNAME_LENGTH,
        unique=True,
        validators=[forbidden_words_validator],
        verbose_name="Имя контакте",
    )
    email = models.EmailField(
        max_length=settings.MAX_EMAIL_LENGTH,
        unique=True,
        validators=[forbidden_words_validator],
        verbose_name="Электронная почта",
    )
    subject = models.CharField(
        max_length=settings.MAX_SUBJECT_LENGTH, verbose_name="Тема письма"
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
