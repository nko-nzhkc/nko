from collections.abc import Callable
from http import HTTPMethod, HTTPStatus
from pathlib import Path

import pytest
import zapros
from faker import Faker
from zapros.mock import Mock

from api.unisender_service.contacts import add_contacts
from contacts.models import Donor
from donor_base.constants import SubscriptionStatuses


@pytest.mark.django_db
def test_add_contacts_not_found_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """HTTP 404 отбрасывается raise_for_status до проверки status."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/missing.csv"
    route = route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NOT_FOUND),
    )

    with pytest.raises(zapros.StatusCodeError) as caught:
        add_contacts(file_url)

    assert caught.value.response.status == HTTPStatus.NOT_FOUND
    route.assert_called_once()


@pytest.mark.django_db
def test_add_contacts_no_content_returns_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """204 проходит raise_for_status и доходит до проверки status == 200."""
    monkeypatch.chdir(tmp_path)
    file_url = "https://files.test/empty.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(status=HTTPStatus.NO_CONTENT),
    )

    assert add_contacts(file_url) == (
        "Файл по ссылке не получен, код ответа 204."
    )
    assert not (tmp_path / "files").exists()


@pytest.mark.django_db
def test_import_new_donors_reuses_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    header: str,
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
) -> None:
    """Существующий каталог переиспользуется, новые доноры импортируются."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "files").mkdir()
    email = faker.unique.email()
    inactive_group_id = SubscriptionStatuses.INACTIVE.group_id
    csv_data = (f"{header}\n{email},{inactive_group_id}\n").encode()
    file_url = "https://files.test/contacts.csv"
    route_zapros_response(
        HTTPMethod.GET,
        file_url,
        zapros.Response(
            status=HTTPStatus.OK,
            content=csv_data,
        ),
    )

    assert add_contacts(file_url) == "Добавлено 1 контактов."
    assert Donor.objects.get(email=email).subscription == (
        SubscriptionStatuses.INACTIVE.capitalized
    )
    assert not (tmp_path / "files").exists()