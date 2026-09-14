# Модуль конфига API.
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Конфиг API."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
