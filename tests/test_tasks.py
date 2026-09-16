"""Тесты Celery-задач API."""

from unittest.mock import patch

import pytest
import zapros
from celery.app.task import Task
from celery.exceptions import Retry

from api.tasks import send_users_to_unisender


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
def use_case_class():
    """Изолирует задачу от выполнения сценария и обращения к БД."""
    with patch("api.tasks.SyncDonorsToUnisenderUseCase") as factory:
        yield factory


@pytest.fixture
def repository_class():
    """Подменяет создание репозитория в задаче."""
    with patch("api.tasks.DonorRepository") as factory:
        yield factory


@pytest.fixture(autouse=True)
def get_unisender_client():
    """Изолирует unit-тесты задачи от DI-контейнера приложения."""
    with patch("api.tasks.di.get_unisender_client") as get_client:
        yield get_client


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
def test_retries_zapros_errors(error, use_case_class, task_retry):
    """Любое исключение zapros приводит к Celery retry."""
    use_case_class.return_value.execute.side_effect = error

    with pytest.raises(Retry):
        send_users_to_unisender.run()

    task_retry.assert_called_once()
    assert task_retry.call_args.kwargs["exc"] is error


def test_executes_use_case(
    use_case_class,
    repository_class,
    get_unisender_client,
    task_retry,
):
    """Задача передаёт клиент из DI и выполняет сценарий."""
    send_users_to_unisender.run()

    repository_class.assert_called_once_with()
    get_unisender_client.assert_called_once_with()
    use_case_class.assert_called_once_with(
        repository=repository_class.return_value,
        client=get_unisender_client.return_value,
    )
    use_case_class.return_value.execute.assert_called_once_with()
    task_retry.assert_not_called()


def test_does_not_retry_unrelated_error(use_case_class, task_retry):
    """Ошибка вне иерархии zapros не приводит к retry."""
    error = ValueError("Invalid data")
    use_case_class.return_value.execute.side_effect = error

    with pytest.raises(ValueError) as caught:
        send_users_to_unisender.run()

    assert caught.value is error
    task_retry.assert_not_called()


def test_retry_configuration():
    """Первый запуск и два повтора дают три попытки."""
    assert send_users_to_unisender.autoretry_for == (zapros.ZaprosError,)
    assert send_users_to_unisender.max_retries == 2
