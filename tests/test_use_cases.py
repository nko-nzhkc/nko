"""Тесты сценариев API."""

from unittest.mock import Mock, call

from django.test import SimpleTestCase, override_settings

from api.use_cases import (
    UNISENDER_BATCH_SIZE,
    UNISENDER_FIELD_NAMES,
    SyncDonorsToUnisenderUseCase,
)


@override_settings(
    GROUPS={
        "Active": "5",
        "Inactive": "7",
        "Lost": "9",
    }
)
class SyncDonorsToUnisenderUseCaseTest(SimpleTestCase):
    """Проверяет пакетную синхронизацию доноров."""

    def test_execute_sends_exactly_one_batch_of_500_donors(self):
        """500 доноров отправляются одним вызовом importContacts."""
        donors = [
            (f"donor-{index}@example.com", "Active")
            for index in range(UNISENDER_BATCH_SIZE)
        ]
        repository = Mock()
        repository.get_donors.return_value = donors
        client = Mock()

        SyncDonorsToUnisenderUseCase(repository, client).execute()

        client.send_contacts_to_unisender.assert_called_once_with(
            field_names=UNISENDER_FIELD_NAMES,
            data=[
                [f"donor-{index}@example.com", "5"]
                for index in range(UNISENDER_BATCH_SIZE)
            ],
            overwrite_lists=1,
        )

    def test_execute_splits_501_donors_into_two_batches(self):
        """501 донор разделяется на пачки 500 и 1."""
        donors = [
            (f"donor-{index}@example.com", "Active")
            for index in range(UNISENDER_BATCH_SIZE + 1)
        ]
        repository = Mock()
        repository.get_donors.return_value = donors
        client = Mock()

        SyncDonorsToUnisenderUseCase(repository, client).execute()

        self.assertEqual(
            client.send_contacts_to_unisender.call_args_list,
            [
                call(
                    field_names=UNISENDER_FIELD_NAMES,
                    data=[
                        [f"donor-{index}@example.com", "5"]
                        for index in range(UNISENDER_BATCH_SIZE)
                    ],
                    overwrite_lists=1,
                ),
                call(
                    field_names=UNISENDER_FIELD_NAMES,
                    data=[
                        [f"donor-{UNISENDER_BATCH_SIZE}@example.com", "5"]
                    ],
                    overwrite_lists=1,
                ),
            ],
        )

    def test_execute_passes_filter_and_overwrite_lists(self):
        """Сценарий передаёт фильтр и сохраняет режим обновления."""
        for overwrite_lists in (0, 1):
            with self.subTest(overwrite_lists=overwrite_lists):
                repository = Mock()
                repository.get_donors.return_value = iter([
                    ("donor@example.com", "Active"),
                ])
                client = Mock()

                SyncDonorsToUnisenderUseCase(
                    repository,
                    client,
                ).execute(
                    donor_ids=[10],
                    overwrite_lists=overwrite_lists,
                )

                repository.get_donors.assert_called_once_with(
                    donor_ids=[10],
                )
                client.send_contacts_to_unisender.assert_called_once_with(
                    field_names=UNISENDER_FIELD_NAMES,
                    data=[["donor@example.com", "5"]],
                    overwrite_lists=overwrite_lists,
                )

    def test_execute_does_not_send_empty_selection(self):
        """Пустая выборка не приводит к отправке контактов."""
        repository = Mock()
        repository.get_donors.return_value = iter([])
        client = Mock()

        SyncDonorsToUnisenderUseCase(repository, client).execute(
            donor_ids=[],
        )

        repository.get_donors.assert_called_once_with(donor_ids=[])
        client.send_contacts_to_unisender.assert_not_called()
