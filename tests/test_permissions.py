"""Тесты разрешений API."""

from types import SimpleNamespace

import pytest

from api.permissions import IsAdmin


@pytest.mark.parametrize(
    "is_authenticated, is_admin, is_superuser, expected",
    [
        (False, False, False, None),
        (True, False, False, False),
        (True, True, False, True),
        (True, False, True, True),
    ],
)
def test_is_admin_permission_branches(
    is_authenticated,
    is_admin,
    is_superuser,
    expected,
):
    """Разрешение учитывает анонимов, админов и суперпользователей."""
    request = SimpleNamespace(
        user=SimpleNamespace(
            is_authenticated=is_authenticated,
            is_admin=is_admin,
            is_superuser=is_superuser,
        )
    )
    permission = IsAdmin()

    assert permission.has_permission(request, object()) is expected
    assert permission.has_object_permission(
        request, object(), object()
        ) is expected
