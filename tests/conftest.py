from typing import Callable

import pytest
from pytest_mock import MockerFixture
from unittest.mock import MagicMock, Mock, PropertyMock


@pytest.fixture
def mock_http_client_with_response(
    mocker: MockerFixture,
) -> tuple[MagicMock, Mock]:
    """Патчит api.utils.http_client и отдаёт (client, response)."""
    client = mocker.patch('api.utils.http_client')
    response = mocker.Mock()
    client.request.return_value = response
    client.post_form.return_value = response
    return client, response


@pytest.fixture
def mock_http_client(
    mock_http_client_with_response: tuple[MagicMock, Mock],
) -> MagicMock:
    """Шорткат только до client, когда response не нужен."""
    client, _ = mock_http_client_with_response
    return client


@pytest.fixture
def mock_http_response(
    mock_http_client_with_response: tuple[MagicMock, Mock],
) -> Mock:
    """Шорткат только до response, когда client не нужен."""
    _, response = mock_http_client_with_response
    return response


@pytest.fixture
def mock_unisender_success(
    mock_http_response: Mock,
) -> Callable[..., dict[str, str]]:
    """Настраивает mock_http_response для успешного сценария Unisender.

    Возвращает фабричную функцию, которая при вызове задаёт на моке
    два последовательных json-ответа: сначала ответ с шаблоном письма
    (URL_GET_TEMP), затем ответ с идентификатором отправленного письма
    (URL_SEND_EMAIL). Сама фабрика возвращает использованный шаблон,
    чтобы тест мог сверить с ним аргументы вызовов.
    """
    def _factory(template=None, email_id="12345"):
        if template is None:
            template = {"subject": "Спасибо", "body": "<h1>Спасибо</h1>"}
        type(mock_http_response).json = PropertyMock(side_effect=[
            {"result": template},
            {"result": {"email_id": email_id}},
        ])
        return template
    return _factory


@pytest.fixture
def mock_unisender_error(
    mock_http_response: Mock,
) -> Callable[[dict[str, str]], None]:
    """Настраивает mock_http_response для сценария с ошибкой Unisender.

    Возвращает фабричную функцию, которая при вызове задаёт на моке
    один json-ответ с полем ``"error"``, имитируя отказ API.
    """
    def _factory(response: dict[str, str]) -> None:
        type(mock_http_response).json = PropertyMock(return_value=response)
    return _factory


@pytest.fixture
def mock_unisender_mixed(
    mock_http_response: Mock,
) -> Callable[..., dict[str, str]]:
    """Настраивает mock_http_response для сценария успех + ошибка.

    Первый json-ответ - успешное получение шаблона (URL_GET_TEMP),
    второй - ошибка отправки письма (URL_SEND_EMAIL).
    Возвращает использованный шаблон для проверки аргументов вызова.
    """
    def _factory(
        template: dict[str, str] | None = None,
        error_response: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if template is None:
            template = {"subject": "Спасибо", "body": "<h1>Спасибо</h1>"}
        if error_response is None:
            error_response = {"error": "Some send error", "code": "send_error"}
        type(mock_http_response).json = PropertyMock(side_effect=[
            {"result": template},
            error_response,
        ])
        return template
    return _factory
