"""Модуль тестов API."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import zapros
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from faker import Faker
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter

from donor_base import http_client
from donor_base.unisender_client import Client

from .utils import (ad_donor, check_cloudpayments_connection,
                    send_payment_email, send_request)


class CloudpaymentsConnectionTest(TestCase):
    """Тест-кейс проверки подключения к api cloudpayments."""

    def test_connection(self):
        """Метод проверки подключения к api cloudpayments."""
        self.assertTrue(check_cloudpayments_connection())


class UnisenderHttpMixin:
    """Общие фикстуры HTTP-тестов Unisender."""

    def setUp(self):
        """Подготавливает общие данные и HTTP-мок."""
        super().setUp()

        self.fake = Faker()
        self.email = self.fake.email()
        self.list_id = self.fake.random_int(min=1)
        self.api_key = self.fake.sha256()

        self.router = MockRouter()
        self.http = zapros.Client(handler=MockMiddleware(self.router))
        self.addCleanup(self.http.close)

        client_patch = patch.object(http_client, "client", new=self.http)
        client_patch.start()
        self.addCleanup(client_patch.stop)

        self._override_settings(UNISENDER_API_KEY=self.api_key)

    def _override_settings(self, **kwargs):
        overridden = self.settings(**kwargs)
        overridden.enable()
        self.addCleanup(overridden.disable)

    def _mock_post(self, url, response_data):
        parsed = urlsplit(url)
        mock = (
            Mock.given(path(parsed.path).method("POST").host(parsed.hostname))
            .respond(zapros.Response(status=200, json=response_data))
            .once()
        )
        self.router.add(mock)
        return mock

    def _assert_form(self, mock, url, expected):
        mock.assert_called_once()
        request = mock.calls[0]

        self.assertEqual(request.url.to_string(), url)
        self.assertEqual(
            request.headers["Content-Type"].split(";", 1)[0],
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(
            parse_qs(request.body.decode("utf-8"), keep_blank_values=True),
            {key: [str(value)] for key, value in expected.items()},
        )


class UnisenderClientTest(UnisenderHttpMixin, SimpleTestCase):
    """Тест HTTP-клиента Unisender."""

    def setUp(self):
        """Подготавливает данные для теста HTTP-клиента Unisender."""
        super().setUp()

        self.platform = self.fake.word()
        self.unisender = Client(
            api_key=self.api_key,
            platform=self.platform,
        )
        self.url = (
            f"{settings.DEFAULT_CONF['base_url']}/"
            f"{settings.DEFAULT_CONF['lang']}/api/importContacts"
        )
        self.data = {
            "field_names": ["email", "email_list_ids"],
            "data": [[self.email, self.list_id]],
            "overwrite_lists": 1,
        }
        self.response_data = {"result": {"total": 1}}
        self.expected_form = {
            "api_key": self.api_key,
            "platform": self.platform,
            "format": settings.DEFAULT_CONF["format"],
            "field_names[0]": "email",
            "field_names[1]": "email_list_ids",
            "data[0][0]": self.email,
            "data[0][1]": self.list_id,
            "overwrite_lists": 1,
        }
        self.import_mock = self._mock_post(self.url, self.response_data)

    def test_api_request_posts_form_to_unisender(self):
        """Проверяет отправку формы в Unisender."""
        response = self.unisender._api_request("import_contacts", self.data)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.json, self.response_data)
        self._assert_form(self.import_mock, self.url, self.expected_form)


class AdDonorTest(UnisenderHttpMixin, TestCase):
    """Тест запроса importContacts при добавлении донора."""

    def setUp(self):
        """Подготавливает данные для теста добавления донора."""
        super().setUp()

        self.subscription = settings.SUBSCRIPTION_CHOICES[0][0]
        self._override_settings(
            GROUPS={self.subscription: str(self.list_id)},
        )
        self.expected_form = {
            "format": "json",
            "api_key": self.api_key,
            "overwrite_lists": 0,
            "field_names[0]": "email",
            "field_names[1]": "email_list_ids",
            "data[0][0]": self.email,
            "data[0][1]": self.list_id,
        }
        self.import_mock = self._mock_post(
            settings.IMPORT_UNISENDER,
            {"result": {"total": 1}},
        )

    def test_ad_donor_posts_to_import_contacts(self):
        """Проверяет отправку донора в importContacts."""
        ad_donor(self.email, self.subscription)

        self._assert_form(
            self.import_mock,
            settings.IMPORT_UNISENDER,
            self.expected_form,
        )


class SendPaymentEmailTest(UnisenderHttpMixin, SimpleTestCase):
    """Тест запросов getTemplate и sendEmail."""

    def setUp(self):
        """Подготавливает данные для теста отправки письма."""
        super().setUp()

        self._override_settings(
            TEMPLATE_ID=self.fake.random_int(min=1),
            DEFAULT_FROM_EMAIL=self.fake.email(),
            UNISENDER_SENDER_NAME=self.fake.company(),
        )
        self.template = {
            "subject": self.fake.sentence(),
            "body": self.fake.text(),
        }
        self.expected_template_form = {
            "format": "json",
            "api_key": self.api_key,
            "template_id": settings.TEMPLATE_ID,
        }
        self.expected_email_form = {
            "format": "json",
            "api_key": self.api_key,
            "email": self.email,
            "sender_email": settings.DEFAULT_FROM_EMAIL,
            "sender_name": settings.UNISENDER_SENDER_NAME,
            "subject": self.template["subject"],
            "body": self.template["body"],
            "list_id": self.list_id,
        }
        self.template_mock = self._mock_post(
            settings.URL_GET_TEMP,
            {"result": self.template},
        )
        self.email_mock = self._mock_post(
            settings.URL_SEND_EMAIL,
            {"result": {"email_id": self.fake.random_int(min=1)}},
        )

    def test_send_payment_email_calls_get_template_and_send_email(self):
        """Проверяет получение шаблона и отправку письма."""
        send_payment_email(self.email, self.list_id)

        self._assert_form(
            self.template_mock,
            settings.URL_GET_TEMP,
            self.expected_template_form,
        )
        self._assert_form(
            self.email_mock,
            settings.URL_SEND_EMAIL,
            self.expected_email_form,
        )


class SendRequestTest(UnisenderHttpMixin, SimpleTestCase):
    """Тест запроса exportContacts."""

    def setUp(self):
        """Подготавливает данные для теста экспорта контактов."""
        super().setUp()

        self.response_data = {
            "result": {"task_uuid": self.fake.uuid4()},
        }
        self.expected_form = {
            "api_key": self.api_key,
            "notify_url": settings.NOTIFY_URL,
            "field_names[0]": "email",
            "field_names[1]": "email_list_ids",
            "list_id": self.list_id,
        }
        self.export_mock = self._mock_post(
            settings.EXPORT_UNISENDER,
            self.response_data,
        )

    def test_send_request_posts_to_export_contacts(self):
        """Проверяет отправку запроса на экспорт контактов."""
        result = send_request(self.list_id)

        self.assertEqual(result, self.response_data)
        self._assert_form(
            self.export_mock,
            settings.EXPORT_UNISENDER,
            self.expected_form,
        )
