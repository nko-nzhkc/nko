"""Общий HTTP-клиент проекта."""

from http import HTTPMethod

from donor_base import di

HTTP_TIMEOUT = 30.0


def _stringify_pair(key, field):
    """Преобразует пару ключ-значение в строки."""
    return str(key), str(field)


def _stringify_form_fields(data):
    """Преобразует данные в строковые поля формы."""
    return dict(
        _stringify_pair(key, field)
        for key, field in data.items()
        if field is not None
    )


def request(method, url, **kwargs):
    """Выполняет HTTP-запрос и проверяет его статус."""
    kwargs.setdefault(
        "context",
        {"timeouts": {"connect": HTTP_TIMEOUT, "read": HTTP_TIMEOUT}},
    )
    response = di.get_client().request(method, url, **kwargs)
    response.raise_for_status()
    return response


def post_form(url, data):
    """Отправляет данные как application/x-www-form-urlencoded."""
    return request(HTTPMethod.POST, url, form=_stringify_form_fields(data))
