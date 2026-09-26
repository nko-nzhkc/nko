# Модуль модели запрещенных слов.
from typing import override

from django.db import models
from donor_base.constants import MAX_FORBIDDEN_WORLD_LENGTH


class ForbiddenWord(models.Model):
    """Модель запрещенных слов."""

    forbidden_word = models.CharField(
        max_length=MAX_FORBIDDEN_WORLD_LENGTH,
        unique=True,
        verbose_name="Запрещенное слово",
    )

    class Meta:
        verbose_name = "Запрещенное слово"
        verbose_name_plural = "Запрещенные слова"

    @override
    def __str__(self) -> str:
        """Строковое представление для модели ForbiddenWord."""
        return self.forbidden_word
