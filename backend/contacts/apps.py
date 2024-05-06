# Модуль конфига контактов.
from django.apps import AppConfig


class ContactsConfig(AppConfig):
    """Конфиг контактов."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "contacts"
    verbose_name = "Контакты"
