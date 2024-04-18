# Модуль конфига пожертвований.
from django.apps import AppConfig


class DonationsConfig(AppConfig):
    """Конфиг пожертвований."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "donations"
    verbose_name = "Пожертвования"

    def ready(self):
        from . import signals
