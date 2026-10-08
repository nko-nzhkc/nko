"""Тесты ошибок Unisender и скачивания CSV."""

from collections.abc import Callable
from http import HTTPMethod, HTTPStatus
from pathlib import Path
from typing import Any

import pytest
import zapros
from django.conf import settings
from faker import Faker
from zapros.mock import Mock

from api.unisender_service import (
    add_contacts,
    send_payment_email,
    send_request,
)
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses


@pytest.mark.parametrize(
    "response_data",
    [
        {"error": "bad request", "code": 400},
        {"unexpected": "payload"},
    ],
)
def test_send_request_returns_none_for_error_payloads(
    response_data: dict[str, Any],
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Error и неизвестный JSON обрабатываются через публичный сервис."""
    route_zapros_response(
        HTTPMethod.POST,
        settings.EXPORT_UNISENDER,
        zapros.Response(
            status=HTTPStatus.OK,
            json=response_data,
        ),
    )

    assert send_request("5") is None


def test_send_payment_email_stops_when_template_is_not_returned(
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """При отсутствии шаблона запрос sendEmail не выполняется."""
    template_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_GET_TEMP,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"error": "template not found", "code": 404},
        ),
    )

    send_payment_email("donor@example.org", "5")

    template_route.assert_called_once()


def test_send_payment_email_handles_send_error(
    settings: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Ошибка sendEmail обрабатывается после получения шаблона."""
    template_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_GET_TEMP,
        zapros.Response(
            status=HTTPStatus.OK,
            json={
                "result": {
                    "subject": "Thank you",
                    "body": "Payment received",
                },
            },
        ),
    )
    email_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_SEND_EMAIL,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"error": "invalid email", "code": 400},
        ),
    )

    send_payment_email("donor@example.org", "5")

    template_route.assert_called_once()
    email_route.assert_called_once()


@pytest.mark.django_db
def test_add_contacts_404_raises_zapros_status_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """HTTP 404 отбрасывается raise_for_status до проверки status."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/missing.csv"
    route = route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NOT_FOUND),
    )

    with pytest.raises(zapros.StatusCodeError) as caught:
        add_contacts(file_url)

    assert caught.value.response.status == HTTPStatus.NOT_FOUND
    route.assert_called_once()


@pytest.mark.django_db
def test_add_contacts_returns_message_for_204_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """204 проходит raise_for_status и доходит до проверки status == 200."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/empty.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NO_CONTENT),
    )

    assert add_contacts(file_url) == (
        "Файл по ссылке не получен, код ответа 204."
    )
    assert not (tmp_path / "files").exists()


@pytest.mark.django_db
def test_add_contacts_imports_new_donors_in_existing_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Существующий каталог переиспользуется, новые доноры импортируются."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "files").mkdir()
    email = faker.unique.email()
    csv_data = (
        "email,email_list_ids\n"
        f"{email},{SubscriptionStatuses.INACTIVE.group_id}\n"
    ).encode("utf-8")
    file_url = "https://files.test/contacts.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(
            status=HTTPStatus.OK,
            content=csv_data,
        ),
    )

    assert add_contacts(file_url) == "Добавлено 1 контактов."
    assert Donor.objects.get(email=email).subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )
    assert not (tmp_path / "files").exists()
