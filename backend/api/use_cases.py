"""Сценарии API."""

from itertools import islice

from donor_base.subscriptions import get_group_by_capitalized


UNISENDER_BATCH_SIZE = 500
UNISENDER_FIELD_NAMES = ["email", "email_list_ids"]


def _iter_batches(iterable, batch_size):
    """Возвращает непустые пачки элементов заданного размера."""
    iterator = iter(iterable)

    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            return
        yield batch


class SyncDonorsToUnisenderUseCase:
    """Синхронизирует всех доноров с Unisender."""

    def __init__(self, repository, client):
        self.repository = repository
        self.client = client

    def execute(self, donor_ids=None, overwrite_lists=1):
        """Отправляет всех доноров пачками, допустимыми Unisender."""
        if overwrite_lists not in (0, 1):
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
