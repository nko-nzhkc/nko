"""Тесты API views/actions."""

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.test import RequestFactory
from rest_framework import status

from api.views import (
    CloudPaymentsViewSet,
    ContactViewSet,
    MixplatViewSet,
    PaymentsListView,
)
from cloudpayments.models import CloudPayment


def test_contact_viewset_start_delegates_to_send_request():
    """Action start запускает exportContacts для указанного списка."""
    request = SimpleNamespace(data={"list_id": "5"})

    with patch("api.views.send_request", return_value={"result": "ok"}) as send:  # noqa: E501
        response = ContactViewSet().start(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"result": "ok"}
    send.assert_called_once_with("5")


def test_contact_viewset_get_contacts_get_returns_ok():
    """GET callback от Unisender подтверждается пустым 200."""
    request = SimpleNamespace(method="GET")

    response = ContactViewSet().get_contacts(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data is None


def test_contact_viewset_get_contacts_post_imports_file():
    """POST callback от Unisender передаёт файл в add_contacts."""
    request = SimpleNamespace(
        method="POST",
        data={"result": {"file_to_download": "https://example.test/data.csv"}},
    )

    with patch("api.views.add_contacts", return_value="Добавлено 1 контактов.") as add:  # noqa: E501
        response = ContactViewSet().get_contacts(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"result": "Добавлено 1 контактов."}
    add.assert_called_once_with("https://example.test/data.csv")


def test_mixplat_viewset_payment_status_delegates_to_handler():
    """Action Mixplat payment_status делегирует обработчику webhook."""
    request = SimpleNamespace(data={"payload": "value"})
    expected = Mock()

    with patch("api.views.mixplat_request_handler", return_value=expected) as handler:  # noqa: E501
        response = MixplatViewSet().payment_status(request)

    assert response is expected
    handler.assert_called_once_with(request)


@pytest.mark.django_db
def test_cloudpayments_viewset_create_cloudpayment_saves_valid_payment():
    """CloudPayments action сохраняет валидный payload сериализатора."""
    payload = {
        "email": "donor@example.com",
        "donat": 100,
        "custom_donat": 0,
        "payment_method": "Visa",
        "monthly_donat": False,
        "subscription": False,
        "payment_id": "payment-1",
        "status": "Completed",
        "currency": "RUB",
        "user_account_id": 1,
        "date_created": "2024-01-02T03:04:05Z",
        "date_processed": "2024-01-02T03:05:05Z",
        "payment_operator": "Cloudpayment",
    }

    with patch("api.views.handling_cloudpayment_data", return_value=payload):
        response = CloudPaymentsViewSet().create_cloudpayment(SimpleNamespace())  # noqa: E501

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"code": 0}
    assert CloudPayment.objects.filter(email="donor@example.com").exists()


@pytest.mark.django_db
def test_cloudpayments_viewset_create_cloudpayment_returns_serializer_errors():
    """Невалидный payload CloudPayments возвращает ошибки сериализатора."""
    with patch("api.views.handling_cloudpayment_data", return_value={}):
        response = CloudPaymentsViewSet().create_cloudpayment(SimpleNamespace())  # noqa: E501

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_payments_list_view_returns_union_of_payments():
    """PaymentsListView возвращает общий список платежей двух операторов."""

    class PaymentsQuery:
        def __init__(self, rows):
            self.rows = rows
            self.ordering = None

        def union(self, other):
            return PaymentsQuery([*self.rows, *other.rows])

        def order_by(self, ordering):
            self.ordering = ordering
            return self

        def values(self):
            return self.rows

    mixplat_rows = [{"email": "mixplat@example.com"}]
    cloudpayment_rows = [{"email": "cloud@example.com"}]

    with (
        patch("api.views.MixPlat.objects.all", return_value=PaymentsQuery(mixplat_rows)),  # noqa: E501
        patch(
            "api.views.CloudPayment.objects.all",
            return_value=PaymentsQuery(cloudpayment_rows),
        ),
    ):
        response = PaymentsListView.as_view()(RequestFactory().get("/payments/"))  # noqa: E501

    assert response.status_code == HTTPStatus.OK
    assert b"mixplat@example.com" in response.content
    assert b"cloud@example.com" in response.content
