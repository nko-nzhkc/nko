"""Celery-задачи API."""

from http import HTTPStatus

import zapros
from django.conf import settings

from api.repositories import DonorRepository
from api.use_cases import SyncDonorsToUnisenderUseCase
from donor_base.celery import app, logger
from donor_base.unisender_client import Client

RETRYABLE_HTTP_STATUSES = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)

RETRYABLE_NETWORK_ERRORS = (
    zapros.ConnectionError,
    zapros.TimeoutError,
    zapros.ReadError,
    zapros.WriteError,
)


@app.task(bind=True, max_retries=2)
def send_users_to_unisender(self):
    """Отправляет доноров в Unisender с retry transient-ошибок."""
    client = Client(
        api_key=settings.UNISENDER_API_KEY,
        platform="donor_base",
        lang="ru",
    )
    use_case = SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=client,
    )

    try:
        use_case.execute()
    except zapros.StatusCodeError as error:
        if error.response.status not in RETRYABLE_HTTP_STATUSES:
            raise

        logger.info(
            "Повторная отправка доноров в Unisender: HTTP %s",
            error.response.status,
        )
        raise self.retry(exc=error)
    except RETRYABLE_NETWORK_ERRORS as error:
        logger.info(
            "Повторная отправка доноров в Unisender: %s",
            error,
        )
        raise self.retry(exc=error)
