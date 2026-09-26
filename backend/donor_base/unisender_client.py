"""Клиент для работы с API Unisender."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict, cast

from django.conf import settings
from dotenv import load_dotenv

load_dotenv()


class UnisenderConfig(TypedDict, total=False):
    """Конфигурация клиента Unisender."""

    api_key: str
    platform: str | None
    format: str
    base_url: str
    lang: str


class Client:
    """Клиент для низкоуровневого доступа к Unisender API."""

    def __init__(
        self,
        api_key: str,
        platform: str | None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует настройки, не меняя settings.DEFAULT_CONF."""
        self._config: UnisenderConfig = cast(
            UnisenderConfig,
            settings.DEFAULT_CONF.copy(),
        )
        self._config["api_key"] = api_key
        self._config["platform"] = platform
        self._config.update(cast(UnisenderConfig, kwargs))

    def send_contacts_to_unisender(
        self,
        field_names: Sequence[str],
        data: Sequence[Any],
        overwrite_lists: int = 0,
    ) -> Any:
        """Отправляет контакты в Unisender."""
        return self._api_request(
            "import_contacts",
            {
                "field_names": field_names,
                "data": data,
                "overwrite_lists": overwrite_lists,
            },
        )

    def _build_request_data(
        self,
        data: Mapping[str, Any],
        extra_key: str | None = None,
    ) -> dict[str, Any]:
        default_request_data: dict[str, Any] = {
            "api_key": self._config["api_key"],
            "platform": self._config["platform"],
            "format": self._config["format"],
        }
        for key, field_value in data.items():
            full_key = (
                f"{extra_key}[{key}]" if isinstance(extra_key, str) else key
            )
            self._merge_value(default_request_data, full_key, field_value)
        return default_request_data

    def _merge_value(
        self,
        target: dict[str, Any],
        full_key: str,
        field_value: Any,
    ) -> None:
        if isinstance(field_value, dict):
            target.update(self._build_request_data(field_value, full_key))
        elif isinstance(field_value, (list, tuple)):
            target.update(
                self._build_request_data(
                    {
                        str(idx): field_val
                        for idx, field_val in enumerate(field_value)
                    },
                    full_key,
                ),
            )
        elif field_value is not None:
            target[full_key] = field_value

    def _to_camel_case(self, snake_case_str: str) -> str:
        parts = snake_case_str.split("_")
        capitalized = (word.capitalize() or "_" for word in parts[1:])
        return parts[0] + "".join(capitalized)

    def _get_request_url(self, method: str) -> str:
        return "{base_url}/{lang}/api/{method}".format(
            base_url=self._config["base_url"],
            lang=self._config["lang"],
            method=self._to_camel_case(method),
        )

    def _api_request(self, method: str, data: Mapping[str, Any]) -> Any:
        from donor_base import http_client

        url = self._get_request_url(method)
        data = self._build_request_data(data, extra_key=None)
        return http_client.post_form(url, data)
