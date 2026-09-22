"""Тесты Celery-задач API."""

from unittest.mock import patch

import pytest
import zapros
from api.tasks import (
    send_payment_email_task,
    send_users_to_unisender,
)
from api.use_cases import UNISENDER_FIELD_NAMES
from celery import chain
from celery.app.task import Task
from celery.exceptions import Retry
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses
from donor_base.subscriptions import get_group_by_capitalized


@pytest.fixture(autouse=True)
def task_retry():
    """Подменяет общий механизм retry для задач этого модуля."""
    with patch.object(
        Task,
        "retry",
        autospec=True,
        side_effect=Retry(),
    ) as retry:
        yield retry


@pytest.fixture
def donors(db, faker):
    """Создаёт доноров для выполнения реального сценария."""
    return [
        Donor.objects.create(
            email=faker.unique.email(),
            subscription=subscription,
        )
        for subscription in (
            SubscriptionStatuses.ACTIVE.capitalized,
            SubscriptionStatuses.INACTIVE.capitalized,
        )
    ]


@pytest.fixture(autouse=True)
def api_request():
    """Изолирует отправку запроса во внешний Unisender."""
    with patch(
        "donor_base.unisender_client.Client._api_request",
    ) as request:
        yield request


@pytest.mark.parametrize(
    "error",
    [
        zapros.ZaprosError("Request failed"),
        zapros.ConnectionError("Connection failed"),
        zapros.TimeoutError("Timed out"),
        zapros.ReadError("Read failed"),
        zapros.WriteError("Write failed"),
        zapros.StatusCodeError(zapros.Response(status=400)),
        zapros.StatusCodeError(zapros.Response(status=503)),
    ],
    ids=["base", "connection", "timeout", "read", "write", "400", "503"],
)
def test_retries_zapros_errors(
    error,
    donors,
    api_request,
    task_retry,
):
    """Любое исключение zapros приводит к Celery retry."""
    api_request.side_effect = error

    with pytest.raises(Retry):
        send_users_to_unisender.run()

    task_retry.assert_called_once()
    assert task_retry.call_args.kwargs["exc"] is error


@pytest.mark.parametrize(
    ("selection", "overwrite_lists"),
    [
        ("all", 1),
        ("selected", 0),
    ],
)
def test_executes_use_case(
    selection,
    overwrite_lists,
    donors,
    api_request,
    task_retry,
):
    """Задача передаёт клиент из DI и выполняет сценарий."""
    if selection == "all":
        selected = donors
        send_users_to_unisender.run()
    else:
        selected = donors[:1]
        send_users_to_unisender.run(
            donor_ids=[selected[0].pk],
            overwrite_lists=overwrite_lists,
        )

    api_request.assert_called_once()
    method, payload = api_request.call_args.args

    assert method == "import_contacts"
    assert payload["field_names"] == UNISENDER_FIELD_NAMES
    assert payload["overwrite_lists"] == overwrite_lists
    assert sorted(payload["data"]) == sorted(
        [
            donor.email,
            get_group_by_capitalized(donor.subscription),
        ]
        for donor in selected
    )

    task_retry.assert_not_called()


def test_does_not_retry_unrelated_error(
    donors,
    api_request,
    task_retry,
):
    """Ошибка вне иерархии zapros не приводит к retry."""
    error = ValueError("Invalid data")
    api_request.side_effect = error

    with pytest.raises(ValueError, match="Invalid data") as caught:
        send_users_to_unisender.run()

    assert caught.value is error
    task_retry.assert_not_called()


def test_retry_configuration():
    """Первый запуск и два повтора дают три попытки."""
    assert send_users_to_unisender.autoretry_for == (zapros.ZaprosError,)
    assert send_users_to_unisender.max_retries == 2


@pytest.mark.parametrize(
    ("error", "expected_exception"),
    [
        (zapros.ConnectionError("Connection failed"), Retry),
        (ValueError("Invalid data"), ValueError),
    ],
)
def test_import_failure_does_not_send_email(
    error,
    expected_exception,
    donors,
    api_request,
):
    """Retry или ошибка импорта не запускает следующую задачу."""
    api_request.side_effect = error
    donor = donors[0]

    workflow = chain(
        send_users_to_unisender.si(
            donor_ids=[donor.pk],
            overwrite_lists=1,
        ),
        send_payment_email_task.si(
            email=donor.email,
            list_id=get_group_by_capitalized(donor.subscription),
        ),
    )

    with (
        patch("api.tasks.send_payment_email_task.run") as send_email,
        pytest.raises(expected_exception),
    ):
        workflow.apply(throw=True)

    send_email.assert_not_called()
