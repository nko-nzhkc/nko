"""Репозитории API."""

from contacts.models import Donor


class DonorRepository:
    """Получает доноров для синхронизации."""

    def get_donors(self):
        """Возвращает email и статус подписки каждого донора."""
        return Donor.objects.values_list(
            "email",
            "subscription",
        ).iterator()
