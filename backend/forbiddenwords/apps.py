# Модуль конфига запрещенных слов.
from django.apps import AppConfig


class ForbiddenwordsConfig(AppConfig):
    """Конфиг запрещенных слов."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "forbiddenwords"
    verbose_name = "Запрещенное слово"
    verbose_name_plural = "Запрещенные слова"
