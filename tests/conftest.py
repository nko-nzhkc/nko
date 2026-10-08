"""Общие фикстуры тестов API."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from http import HTTPMethod
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import dishka
import pytest
import zapros
from faker import Faker
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter

from api import donor_service
from contacts.models import Donor
from donor_base import di
from donor_base.constants import SubscriptionStatuses


@pytest.fixture
def api_client() -> APIClient:
    """Создаёт DRF-клиент для действующих URL приложения."""
    return APIClient()


@pytest.fixture
def zapros_router(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[MockRouter]:
    """Направляет реальный zapros.Client в локальный тестовый router."""
    router = MockRouter()
    client = zapros.Client(handler=MockMiddleware(router))
    container = dishka.make_container(
        context={zapros.Client: client},
    )
    monkeypatch.setattr(di, "container", container)

    try:
        yield router
    finally:
        try:
            router.verify()
        finally:
            container.close()


@pytest.fixture
def route_zapros_response(
    zapros_router: MockRouter,
) -> Callable[[HTTPMethod, str, zapros.Response], Mock]:
    """Регистрирует настоящий zapros.Response на HTTP-границе."""

    def add_response(
        method: HTTPMethod,
        url: str,
        response: zapros.Response,
    ) -> Mock:
        parsed_url = urlsplit(url)
        if parsed_url.hostname is None:
            raise ValueError(f"URL должен содержать hostname: {url}")

        route = (
            Mock
            .given(
                path(parsed_url.path).method(method).host(parsed_url.hostname),
            )
            .respond(response)
            .once()
        )
        zapros_router.add(route)
        return route

    return add_response


@pytest.fixture
def parse_zapros_form() -> Callable[[zapros.Request], dict[str, str]]:
    """Разбирает form-urlencoded тело отправленного zapros.Request."""

    def parse_form(request: zapros.Request) -> dict[str, str]:
        if not isinstance(request.body, bytes):
            raise TypeError("Ожидалось bytes-тело form-urlencoded")

        fields = parse_qs(
            request.body.decode("utf-8"),
            keep_blank_values=True,
        )
        return {key: values[0] for key, values in fields.items()}

    return parse_form


@pytest.fixture
def make_donor(db: object, faker: Faker) -> Callable[..., Donor]:
    """Создаёт реальную запись Donor с указанным состоянием."""

    def create_donor(
        *,
        email: str | None = None,
        subscription: str = SubscriptionStatuses.ACTIVE.capitalized,
        count_declined: int = 0,
    ) -> Donor:
        donor_email = email if email is not None else faker.unique.email()
        return Donor.objects.create(
            email=donor_email,
            subscription=subscription,
            count_declined=count_declined,
        )

    return create_donor


@pytest.fixture
def sync_task(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Подменяет Celery-задачу синхронизации с Unisender."""
    task = MagicMock(name="send_users_to_unisender")
    monkeypatch.setattr(
        donor_service,
        "send_users_to_unisender",
        task,
    )
    return task


@pytest.fixture
def email_task(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Подменяет Celery-задачу отправки письма."""
    task = MagicMock(name="send_payment_email_task")
    monkeypatch.setattr(
        donor_service,
        "send_payment_email_task",
        task,
    )
    return task


@pytest.fixture
def chain_factory(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Подменяет создание Celery chain."""
    factory = MagicMock(name="chain")
    monkeypatch.setattr(donor_service, "chain", factory)
    return factory


@pytest.fixture
def api_request() -> Iterator[MagicMock]:
    """Изолирует отправку запроса во внешний Unisender."""
    with patch(
        "donor_base.unisender_client.Client._api_request",
    ) as request:
        yield request


@pytest.fixture
def drf_json_request() -> Callable[[Any], Request]:
    """Создаёт DRF Request из JSON-тела."""

    def build_request(data: Any) -> Request:
        django_request = APIRequestFactory().post(
            "/",
            data=data,
            format="json",
        )
        return Request(
            django_request,
            parsers=[JSONParser()],
            parser_context={
                "request": django_request,
                "encoding": django_request.encoding,
            },
        )

    return build_request


@pytest.fixture
def cloudpayment_payload(faker: Faker) -> dict[str, Any]:
    """Возвращает валидный по форме CloudPayments webhook payload."""
    return {
        "Model": [
            {
                "Email": faker.unique.email(),
                "Amount": 100,
                "CreatedDateIso": "2024-01-02T03:04:05Z",
                "ConfirmDateIso": "2024-01-02T03:05:05Z",
                "TransactionId": 12345,
                "Status": "Completed",
                "CardType": "Visa",
                "Currency": "RUB",
            },
        ],
    }


@pytest.fixture
def mixplat_payload(faker: Faker) -> dict[str, str | None]:
    """Возвращает валидный Mixplat webhook payload."""
    return {
        "user_email": faker.unique.email(),
        "amount": "100",
        "amount_user": "150",
        "payment_method": "card",
        "payment_id": "payment-1",
        "status": "success",
        "user_account_id": "42",
        "date_created": "2024-01-02 03:04:05",
        "date_processed": "2024-01-02 03:05:05",
        "currency": "RUB",
        "recurrent_id": None,
    }
