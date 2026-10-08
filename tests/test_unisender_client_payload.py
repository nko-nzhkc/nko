"""Тесты сериализации payload клиентом Unisender."""

from collections.abc import Callable
from http import HTTPMethod

import zapros
from donor_base.unisender_client import Client
from zapros.mock import Mock


def test_client_flattens_nested_data_and_omits_none(
    route_zapros_response: Callable[
        [HTTPMethod, str, zapros.Response],
        Mock,
    ],
    parse_zapros_form: Callable[[zapros.Request], dict[str, str]],
) -> None:
    """Реальный клиент flatten-ит вложенные данные и пропускает None."""
    url = "https://unisender.test/en/api/importContacts"
    route = route_zapros_response(
        HTTPMethod.POST,
        url,
        zapros.Response(
            status=200,
            json={"result": {"total": 1}},
        ),
    )
    client = Client(
        api_key="api-key",
        platform=None,
        base_url="https://unisender.test",
        lang="en",
    )

    client.send_contacts_to_unisender(
        field_names=("email", "email_list_ids"),
        data=[
            {
                "outer": {"inner": "value"},
                "skipped": None,
            },
        ],
        overwrite_lists=0,
    )

    assert parse_zapros_form(route.calls[0]) == {
        "api_key": "api-key",
        "format": "json",
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "data[0][outer][inner]": "value",
        "overwrite_lists": "0",
    }
