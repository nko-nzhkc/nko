"""Сценарии API."""

from collections.abc import Iterable, Iterator
from itertools import islice
from typing import Any, Protocol, TypeVar

from donor_base.subscriptions import get_group_by_capitalized

T = TypeVar("T")


class DonorRepository(Protocol):
    """Протокол репозитория доноров."""

    def get_donors(
        self,
        donor_ids: Iterable[int] | None = ...,
    ) -> Iterable[tuple[str, str]]:
        """Возвращает итератор доноров в виде (email, subscription)."""
        ...


class UnisenderClient(Protocol):
    """Протокол клиента Unisender."""

    def send_contacts_to_unisender(
        self,
        *,
        field_names: tuple[str, ...],
        data: list[list[Any]],
        overwrite_lists: int,
    ) -> None:
        """Отправляет контакты в Unisender."""
        ...


UNISENDER_BATCH_SIZE = 500
UNISENDER_FIELD_NAMES = ("email", "email_list_ids")


def _iter_batches[T](
    iterable: Iterable[T],
    batch_size: int,
) -> Iterator[list[T]]:
    """Возвращает непустые пачки элементов заданного размера."""
    iterator = iter(iterable)

    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            return
        yield batch


class SyncDonorsToUnisenderUseCase:
    """Синхронизирует всех доноров с Unisender."""

    def __init__(
        self,
        repository: DonorRepository,
        client: UnisenderClient,
    ) -> None:
        """Инициализирует use case репозиторием доноров и клиентом Unisender.

        Args:
            repository: Репозиторий, предоставляющий метод ``get_donors``
                для получения доноров.
            client: Клиент Unisender с методом
                ``send_contacts_to_unisender``.
        """
        self.repository = repository
        self.client = client

    def execute(
        self,
        donor_ids: Iterable[int] | None = None,
        overwrite_lists: int = 1,
    ) -> None:
        """Отправляет всех доноров пачками, допустимыми Unisender."""
        if overwrite_lists not in {0, 1}:
            raise ValueError("overwrite_lists должен быть равен 0 или 1")

        donors = self.repository.get_donors(donor_ids=donor_ids)

        for donor_batch in _iter_batches(donors, UNISENDER_BATCH_SIZE):
            self.client.send_contacts_to_unisender(
                field_names=UNISENDER_FIELD_NAMES,
                data=[
                    [email, get_group_by_capitalized(subscription)]
                    for email, subscription in donor_batch
                ],
                overwrite_lists=overwrite_lists,
            )
