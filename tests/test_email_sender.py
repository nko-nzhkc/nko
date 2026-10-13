from collections.abc import Callable
from http import HTTPMethod, HTTPStatus
from typing import Any

import pytest
import zapros
from pytest_django import Settings
from zapros.mock import Mock

from api.unisender_service.email_sender import (
    send_payment_email,
    send_request,
)


@pytest.mark.parametrize(
    "response_data",
    [
        {"error": "bad request", "code": 400},
        {"unexpected": "payload"},
    ],
)
def test_send_request_none_for_error_payloads(
    settings: Settings,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    *,
    response_data: dict[str, Any],
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


def test_send_email_stops_without_template(
    settings: Settings,
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
    settings: Settings,
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