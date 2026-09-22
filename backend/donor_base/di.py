"""DI-контейнер приложения на Dishka."""

from collections.abc import Generator

import dishka
import zapros
from django.conf import settings

from donor_base.unisender_client import Client as UnisenderClient


class AppProvider(dishka.Provider):
    """Провайдер зависимостей приложения."""

    @dishka.provide(scope=dishka.Scope.APP)
    def http_client(self) -> Generator[zapros.Client]:
        """Создаёт и закрывает общий HTTP-клиент."""
        client = zapros.Client(
            handler=zapros.RedirectMiddleware(zapros.StdNetworkHandler()),
        )
        yield client
        client.close()

    @dishka.provide(scope=dishka.Scope.APP)
    def unisender_client(self) -> UnisenderClient:
        """Создаёт общий клиент Unisender."""
        return UnisenderClient(
            api_key=settings.UNISENDER_API_KEY,
            platform="donor_base",
            lang="ru",
        )


container = dishka.make_container(AppProvider())


def get_client() -> zapros.Client:
    """Возвращает общий HTTP-клиент приложения."""
    return container.get(zapros.Client)


def get_unisender_client() -> UnisenderClient:
    """Возвращает общий клиент Unisender."""
    return container.get(UnisenderClient)
