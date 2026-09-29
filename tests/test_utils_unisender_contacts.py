"""Тесты Unisender helpers и импорта контактов из api.utils."""

from http import HTTPStatus
from unittest.mock import Mock, call, patch

import pytest

from api.utils import (
    _extract_unisender_result,
    add_contacts,
    send_payment_email,
    send_request,
)
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses


def assert_donor(email, subscription):
    """Проверяет подписку сохранённого донора."""
    donor = Donor.objects.get(email=email)
    assert donor.subscription == subscription
    return donor


@pytest.mark.parametrize(
    "response_data",
    [
        {"error": "bad request", "code": 400},
        {"unexpected": "payload"},
    ],
)
def test_extract_unisender_result_returns_none_for_errors(response_data):
    """Ошибки и неизвестные ответы Unisender превращаются в None."""
    assert _extract_unisender_result(response_data) is None


def test_send_payment_email_stops_when_template_is_not_returned(settings):
    """Если шаблон не получен, письмо не отправляется."""
    template_response = Mock(json={"error": "not found", "code": 404})

    with patch(
        "api.utils.http_client.post_form",
        return_value=template_response
    ) as post_form:
        send_payment_email("donor@example.com", "5")

    post_form.assert_called_once_with(
        settings.URL_GET_TEMP,
        {
            "format": "json",
            "api_key": settings.UNISENDER_API_KEY,
            "template_id": settings.TEMPLATE_ID,
        },
    )


def test_send_payment_email_handles_send_error(settings):
    """Ошибка sendEmail не ломает выполнение после успешного getTemplate."""
    template_response = Mock(
        json={"result": {"subject": "Subject", "body": "Body"}}
    )
    send_response = Mock(json={"error": "bad email", "code": 400})

    with patch(
        "api.utils.http_client.post_form",
        side_effect=[template_response, send_response],
    ) as post_form:
        send_payment_email("donor@example.com", "5")

    assert post_form.call_args_list == [
        call(
            settings.URL_GET_TEMP,
            {
                "format": "json",
                "api_key": settings.UNISENDER_API_KEY,
                "template_id": settings.TEMPLATE_ID,
            },
        ),
        call(
            settings.URL_SEND_EMAIL,
            {
                "format": "json",
                "api_key": settings.UNISENDER_API_KEY,
                "email": "donor@example.com",
                "sender_email": settings.DEFAULT_FROM_EMAIL,
                "sender_name": settings.UNISENDER_SENDER_NAME,
                "subject": "Subject",
                "body": "Body",
                "list_id": "5",
            },
        ),
    ]


@pytest.mark.parametrize(
    "response_data",
    [
        {"error": "failed", "code": 500},
        {"unknown": "payload"},
    ],
)
def test_send_request_returns_none_for_unisender_errors(
    settings,
    response_data
):
    """Ошибочный exportContacts возвращает None вместо payload."""
    with patch(
        "api.utils.http_client.post_form",
        return_value=Mock(json=response_data),
    ):
        assert send_request("5") is None


@pytest.mark.django_db
def test_add_contacts_returns_message_for_failed_download():
    """Если CSV не скачан, доноры не создаются."""
    response = Mock(status=HTTPStatus.NOT_FOUND)

    with patch("api.utils.http_client.request", return_value=response):
        result = add_contacts("https://example.test/data.csv")

    assert result == "Файл по ссылке не получен, код ответа 404."


@pytest.mark.django_db
def test_add_contacts_imports_only_new_donors(tmp_path, monkeypatch, faker):
    """CSV import пропускает заголовок и уже существующих доноров."""
    monkeypatch.chdir(tmp_path)
    existing = Donor.objects.create(
        email=faker.unique.email(),
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    new_email = "new@example.com"
    csv_data = (
        "email,email_list_ids\n"
        f"{existing.email},{SubscriptionStatuses.ACTIVE.group_id}\n"
        f"{new_email},{SubscriptionStatuses.INACTIVE.group_id}\n"
    ).encode()
    response = Mock(status=HTTPStatus.OK)
    response.read.return_value = csv_data

    with patch("api.utils.http_client.request", return_value=response):
        result = add_contacts("https://example.test/data.csv")

    assert result == "Добавлено 1 контактов."
    assert_donor(new_email, SubscriptionStatuses.INACTIVE.capitalized)
    assert not (tmp_path / "files").exists()


@pytest.mark.django_db
def test_add_contacts_uses_existing_files_directory(tmp_path, monkeypatch):
    """Если временная директория уже есть, импорт использует её повторно."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "files").mkdir()
    response = Mock(status=HTTPStatus.OK)
    response.read.return_value = (
        "email,email_list_ids\n"
        f"first@example.com,{SubscriptionStatuses.ACTIVE.group_id}\n"
    ).encode()

    with patch("api.utils.http_client.request", return_value=response):
        result = add_contacts("https://example.test/data.csv")

    assert result == "Добавлено 1 контактов."
    assert_donor("first@example.com", SubscriptionStatuses.ACTIVE.capitalized)
