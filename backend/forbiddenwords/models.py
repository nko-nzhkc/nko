# Модуль модели запрещенных слов.
from django.conf import settings
from django.db import models


class ForbiddenWord(models.Model):
    """Модель запрещенных слов."""

    forbidden_word = models.CharField(
        max_length=settings.MAX_FORBIDDEN_WORLD_LENGTH,
        unique=True,
        verbose_name="Запрещенное слово",
    )

    class Meta:
        verbose_name = "Запрещенное слово"
        verbose_name_plural = "Запрещенные слова"

    def __str__(self):
        return self.forbidden_word
