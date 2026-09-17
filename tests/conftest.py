import pytest


@pytest.fixture
def mock_http_client_with_response(mocker):
    """Патчит api.utils.http_client и отдаёт (client, response)."""
    client = mocker.patch('api.utils.http_client')
    response = mocker.Mock()
    client.request.return_value = response
    return client, response


@pytest.fixture
def mock_http_client(mock_http_client_with_response):
    """Шорткат только до client, когда response не нужен."""
    client, _ = mock_http_client_with_response
    return client


@pytest.fixture
def mock_http_response(mock_http_client_with_response):
    """Шорткат только до response, когда client не нужен."""
    _, response = mock_http_client_with_response
    return response
