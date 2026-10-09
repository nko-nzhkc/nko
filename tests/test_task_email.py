"""Тест передачи письма через Celery task и Unisender service."""

from collections.abc import Callable
from http import HTTPMethod, HTTPStatus

import zapros
from pytest_django import Settings
from zapros.mock import Mock

from api.tasks import send_payment_email_task


def test_email_task_uses_unisender_service(
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    parse_zapros_form: Callable[[zapros.Request], dict[str, str]],
) -> None:
    """Celery task отправляет запросы через реальный zapros.Client."""
    settings.UNISENDER_API_KEY = "test-api-key"
    settings.TEMPLATE_ID = "42"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.org"
    settings.UNISENDER_SENDER_NAME = "Test project"

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
            json={"result": {"email_id": 123}},
        ),
    )

    send_payment_email_task.run("donor@example.org", 5)

    assert parse_zapros_form(template_route.calls[0]) == {
        "format": "json",
        "api_key": "test-api-key",
        "template_id": "42",
    }
    assert parse_zapros_form(email_route.calls[0]) == {
        "format": "json",
        "api_key": "test-api-key",
        "email": "donor@example.org",
        "sender_email": "noreply@example.org",
        "sender_name": "Test project",
        "subject": "Thank you",
        "body": "Payment received",
        "list_id": "5",
    }
