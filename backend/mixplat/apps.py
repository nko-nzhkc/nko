# Модуль конфига платежа Mixplat.
from django.apps import AppConfig


class MixplatConfig(AppConfig):
    """Конфиг платежа Mixplat."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "mixplat"
    verbose_name = "Платежы Mixplat"
