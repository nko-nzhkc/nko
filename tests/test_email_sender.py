"""Тесты запросов шаблона, отправки письма и проверки согласия."""

from collections.abc import Callable
from functools import partial
from http import HTTPMethod, HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import zapros
from pytest_django import Settings
from zapros.mock import Mock

from api.tasks import send_payment_email_task
from api.unisender_service.email_sender import (
    send_payment_email,
    send_request,
)
from contacts.models import Donor
from donor_base import http_client

TEST_LIST_ID = "5"


def _get_template(
    url: str,
    data: Any,
    *,
    donor: Donor,
    settings: Settings,
) -> SimpleNamespace:
    """Возвращает шаблон, сняв согласие во время HTTP-запроса."""
    assert url == settings.URL_GET_TEMP
    assert "email" not in data
    Donor.objects.filter(pk=donor.pk).update(
        email_marketing_consent=False,
    )
    return SimpleNamespace(
        json={
            "result": {
                "subject": "Thank you",
                "body": "Payment received",
            },
        },
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

    assert send_request(TEST_LIST_ID) is None


def test_send_email_stops_without_template(
    settings: Settings,
    make_donor: Callable[..., Donor],
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """При отсутствии шаблона запрос sendEmail не выполняется."""
    donor = make_donor(email_marketing_consent=True)
    template_route = route_zapros_response(
        HTTPMethod.POST,
        settings.URL_GET_TEMP,
        zapros.Response(
            status=HTTPStatus.OK,
            json={"error": "template not found", "code": 404},
        ),
    )

    send_payment_email(donor.email, TEST_LIST_ID)

    template_route.assert_called_once()


def test_send_payment_email_handles_send_error(
    settings: Settings,
    make_donor: Callable[..., Donor],
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Ошибка sendEmail обрабатывается после получения шаблона."""
    donor = make_donor(email_marketing_consent=True)
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

    send_payment_email(donor.email, TEST_LIST_ID)

    template_route.assert_called_once()
    email_route.assert_called_once()


@pytest.mark.parametrize("through_task", [False, True])
@pytest.mark.parametrize("donor_exists", [False, True])
def test_email_without_consent_skips_http(
    make_donor: Callable[..., Donor],
    monkeypatch: pytest.MonkeyPatch,
    *,
    through_task: bool,
    donor_exists: bool,
) -> None:
    """Прямой вызов и задача не передают неподтверждённый адрес."""
    email = "donor@example.org"
    if donor_exists:
        donor = make_donor(
            email=email,
            email_marketing_consent=True,
        )
        # Имитируем изменение после постановки задачи.
        Donor.objects.filter(pk=donor.pk).update(
            email_marketing_consent=False,
        )

    post_form = MagicMock()
    monkeypatch.setattr(http_client, "post_form", post_form)

    if through_task:
        send_payment_email_task.run(email, int(TEST_LIST_ID))
    else:
        send_payment_email(email, TEST_LIST_ID)

    post_form.assert_not_called()


def test_consent_change_blocks_email(
    settings: Settings,
    make_donor: Callable[..., Donor],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Изменение разрешения при запросе шаблона блокирует sendEmail."""
    donor = make_donor(email_marketing_consent=True)
    post_form = MagicMock(
        side_effect=partial(
            _get_template,
            donor=donor,
            settings=settings,
        ),
    )
    monkeypatch.setattr(http_client, "post_form", post_form)

    send_payment_email(donor.email, TEST_LIST_ID)

    post_form.assert_called_once()
    assert post_form.call_args.args[0] == settings.URL_GET_TEMP
    assert "email" not in post_form.call_args.args[1]
