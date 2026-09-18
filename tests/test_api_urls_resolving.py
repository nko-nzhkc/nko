import pytest
from django.test import Client
from django.urls import NoReverseMatch, resolve, reverse
from rest_framework import status
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from api.views import (
    CloudPaymentsViewSet,
    ContactViewSet,
    ForbiddenwordViewSet,
    MixplatViewSet,
    PaymentsListView,
)


def test_api_root_include_uses_correct_namespace() -> None:
    """Проверяет, что маршруты api/ резолвятся с namespace "api"."""
    match = resolve("/api/contacts/")
    assert match.namespace == "api"


def test_api_root_endpoint() -> None:
    """Проверяет, что DefaultRouter создаёт api-root endpoint."""
    client = Client()
    response = client.get("/api/")
    assert response.status_code == status.HTTP_200_OK
    assert "contacts" in response.json()
    assert "forbiddenwords" in response.json()
    assert "mixplat" in response.json()


@pytest.mark.parametrize(
    "frozen_url",
    [
        "/api/mixplat/payment_status/",
        "/api/cloudpayments/create_cloudpayment/",
    ],
    ids=["mixplat_webhook", "cloudpayments_webhook"],
)
def test_webhook_url_is_frozen(frozen_url: str) -> None:
    """Проверяет, что публичные webhook-пути не изменились."""
    assert resolve(frozen_url) is not None


@pytest.mark.parametrize(
    "url, expected_url, expected_view, expected_actions",
    [
        (
            reverse("api:contacts-list"),
            "/api/contacts/",
            ContactViewSet,
            None,
        ),
        (
            reverse("api:contacts-detail", kwargs={"pk": 1}),
            "/api/contacts/1/",
            ContactViewSet,
            None,
        ),
        (
            reverse("api:contacts-start"),
            "/api/contacts/start/",
            ContactViewSet,
            {"post": "start"},
        ),
        (
            reverse("api:contacts-get-contacts"),
            "/api/contacts/get_contacts/",
            ContactViewSet,
            {
                "get": "get_contacts",
                "post": "get_contacts",
            },
        ),
        (
            reverse("api:forbiddenwords-list"),
            "/api/forbiddenwords/",
            ForbiddenwordViewSet,
            None,
        ),
        (
            reverse("api:mixplat-list"),
            "/api/mixplat/",
            MixplatViewSet,
            None,
        ),
        (
            reverse("api:mixplat-payment-status"),
            "/api/mixplat/payment_status/",
            MixplatViewSet,
            {"post": "payment_status"},
        ),
        (
            reverse("api:mixplat-detail", kwargs={"pk": 1}),
            "/api/mixplat/1/",
            MixplatViewSet,
            None,
        ),
        (
            reverse("api:payments_list"),
            "/api/payments/",
            PaymentsListView,
            None,
        ),
        (
            reverse("api:cloudpayments-create-cloudpayment"),
            "/api/cloudpayments/create_cloudpayment/",
            CloudPaymentsViewSet,
            {"post": "create_cloudpayment"},
        )
    ],
    ids=[
        "contacts-list",
        "contacts-detail",
        "contacts-start",
        "contacts-get-contacts",
        "forbiddenwords-list",
        "mixplat-list",
        "mixplat-payment-status",
        "mixplat-detail",
        "payments-list",
        "cloudpayments-create-cloudpayment",
    ],
)
def test_url_resolves_view_and_actions(
    url: str,
    expected_url: str,
    expected_view: type,
    expected_actions: dict[str, str] | None,
) -> None:
    """Проверяет, что маршрут ведёт на корректный View/ViewSet."""
    assert url == expected_url

    resolved_func = resolve(url).func
    is_viewset = issubclass(
        expected_view, (ModelViewSet, GenericViewSet)
    )
    actual_view = resolved_func.cls if is_viewset else resolved_func.view_class

    assert actual_view is expected_view

    if expected_actions:
        assert resolved_func.actions == expected_actions


def test_forbiddenwords_detail_url_not_registered() -> None:
    """Проверяет отсутствие detail-маршрута у ForbiddenwordViewSet."""
    with pytest.raises(NoReverseMatch):
        reverse("api:forbiddenwords-detail", kwargs={"pk": 1})
