"""Репозитории API."""

from collections.abc import Iterable, Iterator

from contacts.models import Donor


class DonorRepository:
    """Получает доноров для синхронизации."""

    def get_donors(
        self,
        donor_ids: Iterable[int] | None = None,
    ) -> Iterator[tuple[str, str]]:
        """Возвращает email и статус подписки каждого донора."""
        queryset = Donor.objects.all()

        if donor_ids is not None:
            queryset = queryset.filter(pk__in=donor_ids)

        return queryset.values_list(
            "email",
            "subscription",
        ).iterator()
