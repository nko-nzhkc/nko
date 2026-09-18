import pytest
from django.contrib.auth.models import AbstractUser
from django.test import Client
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_admin_login_page_accessible(client: Client) -> None:
    """Проверяет, что неавторизованный пользователь видит страницу логина."""
    response = client.get(reverse("admin:index"))
    assert response.status_code == status.HTTP_302_FOUND

    expected_url = f"{reverse('admin:login')}?next={reverse('admin:index')}"
    assert response.url == expected_url


def test_admin_login_page_renders(client: Client) -> None:
    """Проверяет, что /admin/login/ открывается напрямую."""
    response = client.get(reverse("admin:login"))
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_admin_accessible_for_superuser(
    client: Client,
    admin_user: AbstractUser
) -> None:
    """Проверяет доступ суперпользователя к главной странице админки."""
    client.force_login(admin_user)
    response = client.get(reverse("admin:index"))
    assert response.status_code == status.HTTP_200_OK
    assert "admin/index.html" in [
        template.name for template in response.templates
    ]
