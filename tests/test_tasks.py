"""Тесты Celery-задач API."""

from http import HTTPStatus
from unittest.mock import patch

import zapros
from celery.exceptions import Retry
from django.test import SimpleTestCase

from api.tasks import send_users_to_unisender


class SendUsersToUnisenderTaskTest(SimpleTestCase):
    """Проверяет retry задачи синхронизации доноров."""

    @patch("api.tasks.SyncDonorsToUnisenderUseCase")
    def test_retries_network_error(self, use_case_class):
        """Сетевая ошибка приводит к Celery retry."""
        use_case_class.return_value.execute.side_effect = (
            zapros.ConnectionError("Connection failed")
        )

        with patch.object(
            send_users_to_unisender,
            "retry",
            side_effect=Retry(),
        ) as retry:
            with self.assertRaises(Retry):
                send_users_to_unisender.run()

        retry.assert_called_once()
        self.assertIsInstance(
            retry.call_args.kwargs["exc"],
            zapros.ConnectionError,
        )

    @patch("api.tasks.SyncDonorsToUnisenderUseCase")
    def test_retries_http_503(self, use_case_class):
        """HTTP 503 приводит к Celery retry."""
        response = zapros.Response(
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )
        use_case_class.return_value.execute.side_effect = (
            zapros.StatusCodeError(response)
        )
        with patch.object(
            send_users_to_unisender,
            "retry",
            side_effect=Retry(),
        ) as retry:
            with self.assertRaises(Retry):
                send_users_to_unisender.run()

        retry.assert_called_once()
        self.assertIsInstance(
            retry.call_args.kwargs["exc"],
            zapros.StatusCodeError,
        )

    @patch("api.tasks.SyncDonorsToUnisenderUseCase")
    def test_does_not_retry_http_400(self, use_case_class):
        """HTTP 400 остаётся ошибкой задачи без retry."""
        response = zapros.Response(status=HTTPStatus.BAD_REQUEST)
        error = zapros.StatusCodeError(response)
        use_case_class.return_value.execute.side_effect = error

        with self.assertRaises(zapros.StatusCodeError):
            send_users_to_unisender.run()
