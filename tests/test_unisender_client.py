"""Тесты публичных операций клиента Unisender."""

from unittest.mock import patch

import pytest

from donor_base.unisender_client import Client


@pytest.fixture
def client():
    """Создаёт клиент для проверки публичного метода."""
    return Client(
        api_key="api-key",
        platform="donor_base",
        lang="ru",
    )


def test_send_contacts_to_unisender_delegates_to_api_request(client):
    """Публичный метод формирует payload importContacts."""
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
