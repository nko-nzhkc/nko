"""Общий HTTP-клиент проекта."""

import atexit

import zapros

HTTP_TIMEOUT = 30.0

client = zapros.Client(
    handler=zapros.RedirectMiddleware(zapros.StdNetworkHandler())
)
atexit.register(client.close)


def _prepare_form_data(data):
    """Подготавливает данные для отправки формы."""
    return {
        str(key): str(value)
        for key, value in data.items()
        if value is not None
    }


def request(method, url, **kwargs):
    """Выполнить запрос общим клиентом и проверить HTTP-статус."""
    kwargs.setdefault(
        "context",
        {"timeouts": {"connect": HTTP_TIMEOUT, "read": HTTP_TIMEOUT}},
    )
    response = client.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def post_form(url, data):
    """Отправить application/x-www-form-urlencoded."""
    return request("POST", url, form=_prepare_form_data(data))
