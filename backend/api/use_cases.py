"""Сценарии API."""

from itertools import islice

from django.conf import settings


UNISENDER_BATCH_SIZE = 500
UNISENDER_FIELD_NAMES = ["email", "email_list_ids"]


def _iter_batches(iterable, batch_size):
    """Возвращает непустые пачки элементов заданного размера."""
    iterator = iter(iterable)

    while batch := list(islice(iterator, batch_size)):
        yield batch


class SyncDonorsToUnisenderUseCase:
    """Синхронизирует всех доноров с Unisender."""

    def __init__(self, repository, client):
        self.repository = repository
        self.client = client

    def execute(self):
        """Отправляет всех доноров пачками, допустимыми Unisender."""
        donors = self.repository.get_donors()

        for donor_batch in _iter_batches(donors, UNISENDER_BATCH_SIZE):
            self.client.import_contacts(
                field_names=UNISENDER_FIELD_NAMES,
                data=[
                    [email, settings.GROUPS[subscription]]
                    for email, subscription in donor_batch
                ],
                overwrite_lists=1,
            )
