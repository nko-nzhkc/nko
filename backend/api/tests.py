from django.test import TestCase

from .utils import check_cloudpayments_connection


class CloudpaymentsConnectionTest(TestCase):
    """Тест-кейс проверки подключения к api cloudpayments."""

    def test_connection(self):
        """Метод проверки подключения к api cloudpayments."""
        self.assertTrue(check_cloudpayments_connection())
