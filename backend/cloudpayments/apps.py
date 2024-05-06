# Модуль конфига пожертвований Cloudpayments.
from django.apps import AppConfig


class CloudpaymentsConfig(AppConfig):
    """Конфиг пожертвования Cloudpayment."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "cloudpayments"
    verbose_name = "Пожертвования Cloudpayment"
