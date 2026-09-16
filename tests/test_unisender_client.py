"""Тесты публичных операций клиента Unisender."""

from unittest.mock import patch

from django.test import SimpleTestCase

from donor_base.unisender_client import Client


class UnisenderClientSendContactsTest(SimpleTestCase):
    """Проверяет отправку контактов в Unisender."""

    def test_send_contacts_to_unisender_delegates_to_api_request(self):
        """Публичный метод формирует payload importContacts."""
        client = Client(
            api_key="api-key",
            platform="donor_base",
            lang="ru",
        )

        with patch.object(client, "_api_request") as api_request:
            client.send_contacts_to_unisender(
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
