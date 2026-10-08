"""Тесты contact actions и объединённого списка платежей."""

from collections.abc import Callable
from http import HTTPMethod, HTTPStatus
from typing import Any

import pytest
import zapros
from django.utils import timezone
from faker import Faker
from pytest_django import Settings
from rest_framework.test import APIClient
from zapros.mock import Mock

from cloudpayments.models import CloudPayment
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses
from mixplat.models import MixPlat


def test_contact_start_sends_export_request(
    api_client: APIClient,
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    parse_zapros_form: Callable[[zapros.Request], dict[str, str]],
) -> None:
    """start вызывает Unisender exportContacts и возвращает его payload."""
    settings.UNISENDER_API_KEY = "test-api-key"
    settings.NOTIFY_URL = "https://notify.test/callback"
    settings.EXPORT_UNISENDER = "https://unisender.test/export"
    route = route_zapros_response(
        HTTPMethod.POST,
        settings.EXPORT_UNISENDER,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"result": {"task_uuid": "task-1"}},
        ),
    )

    response = api_client.post(
        "/api/contacts/start/",
        data={"list_id": "5"},
        format="json",
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "result": {"task_uuid": "task-1"},
    }
    assert parse_zapros_form(route.calls[0]) == {
        "api_key": "test-api-key",
        "notify_url": "https://notify.test/callback",
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "list_id": "5",
    }


def test_contact_get_contacts_get_returns_empty_ok(
    api_client: APIClient,
) -> None:
    """GET callback получает пустой HTTP 200."""
    response = api_client.get("/api/contacts/get_contacts/")

    assert response.status_code == HTTPStatus.OK
    assert response.content == b""


@pytest.mark.parametrize(
    "url",
    [
        "/api/contacts/start/",
        "/api/contacts/get_contacts/",
    ],
)
def test_contact_post_actions_reject_non_object_payload(
    api_client: APIClient,
    *,
    url: str,
) -> None:
    """POST actions отклоняют JSON-массив вместо объекта."""
    response = api_client.post(url, data=[], format="json")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": "Expected an object."}


@pytest.mark.django_db
def test_contact_callback_imports_only_new_donors(
    api_client: APIClient,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    make_donor: Any,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """POST callback скачивает CSV.

    Пропускает дубликат и импортирует нового.
    """
    monkeypatch.chdir(tmp_path)
    existing_email = faker.unique.email()
    make_donor(
        email=existing_email,
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    new_email = faker.unique.email()
    file_url = "https://files.test/contacts.csv"
    csv_data = (
        "email,email_list_ids\n"
        f"{existing_email},{SubscriptionStatuses.ACTIVE.group_id}\n"
        f"{new_email},{SubscriptionStatuses.INACTIVE.group_id}\n"
    ).encode("utf-8")
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(
            status=HTTPStatus.OK,
            content=csv_data,
        ),
    )

    response = api_client.post(
        "/api/contacts/get_contacts/",
        data={"result": {"file_to_download": file_url}},
        format="json",
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "result": "Добавлено 1 контактов.",
    }
    assert Donor.objects.count() == 2
    assert Donor.objects.get(email=existing_email).subscription == (
        SubscriptionStatuses.ACTIVE.capitalized
    )
    assert Donor.objects.get(email=new_email).subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )


@pytest.mark.django_db
def test_payments_list_returns_union_from_real_querysets(
    api_client: APIClient,
    faker: Faker,
) -> None:
    """Endpoint возвращает платежи из двух настоящих QuerySet."""
    created_at = timezone.now()
    payment_fields: dict[str, Any] = {
        "donat": 100,
        "custom_donat": 0,
        "payment_method": "card",
        "monthly_donat": False,
        "subscription": False,
        "status": "Completed",
        "user_account_id": 42,
        "date_created": created_at,
        "date_processed": created_at,
        "currency": "RUB",
    }
    cloud_email = faker.unique.email()
    mixplat_email = faker.unique.email()

    CloudPayment.objects.create(
        email=cloud_email,
        payment_id="cloud-1",
        payment_operator="CloudPayments",
        **payment_fields,
    )
    MixPlat.objects.create(
        email=mixplat_email,
        payment_id="mixplat-1",
        payment_operator="Mixplat",
        **payment_fields,
    )

    response = api_client.get("/api/payments/")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["count"] == 2
    assert {item["email"] for item in payload["results"]} == {
        cloud_email,
        mixplat_email,
    }
