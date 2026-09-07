"""DI-контейнер приложения на Dishka."""

from collections.abc import Generator

import dishka
import zapros


class AppProvider(dishka.Provider):
    """Провайдер зависимостей приложения."""

    @dishka.provide(scope=dishka.Scope.APP)
    def http_client(self) -> Generator["zapros.Client", None, None]:
        """Создаёт и закрывает общий HTTP-клиент."""
        client = zapros.Client(
            handler=zapros.RedirectMiddleware(zapros.StdNetworkHandler())
        )
        yield client
        client.close()


container = dishka.make_container(AppProvider())


def get_client() -> "zapros.Client":
    """Возвращает общий HTTP-клиент приложения."""
    return container.get(zapros.Client)
