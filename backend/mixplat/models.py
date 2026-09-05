# Модуль модели платежа Mixplat.
from donor_base.base_model import BaseModelDonation


class MixPlat(BaseModelDonation):
    """Модель платежа Mixplat."""

    class Meta:
        ordering = ("-pub_date", "status")
        verbose_name = "Платеж Mixplat"
        verbose_name_plural = "Платежы Mixplat"
