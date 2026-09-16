"""Тесты публичных операций клиента Unisender."""

from unittest.mock import patch

from django.test import SimpleTestCase

from donor_base.unisender_client import Client


class UnisenderClientImportContactsTest(SimpleTestCase):
    """Проверяет публичный метод importContacts."""

    def test_import_contacts_delegates_to_api_request(self):
        """Публичный метод формирует payload importContacts."""
        client = Client(
            api_key="api-key",
            platform="donor_base",
            lang="ru",
        )

        with patch.object(client, "_api_request") as api_request:
            client.import_contacts(
                field_names=["email", "email_list_ids"],
                data=[["donor@example.com", "5"]],
                overwrite_lists=1,
            )

        api_request.assert_called_once_with(
            "import_contacts",
            {
                "field_names": ["email", "email_list_ids"],
                "data": [["donor@example.com", "5"]],
                "overwrite_lists": 1,
            },
        )
