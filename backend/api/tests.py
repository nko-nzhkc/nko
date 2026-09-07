"""Модуль тестов API."""

from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import dishka
import zapros
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from faker import Faker
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter

from donor_base import di
from donor_base.unisender_client import Client

from .utils import (ad_donor, check_cloudpayments_connection,
                    send_payment_email, send_request)

FIELD_NAMES = {
    "field_names[0]": "email",
    "field_names[1]": "email_list_ids",
}


class CloudpaymentsConnectionTest(TestCase):
    """Тест-кейс проверки подключения к api cloudpayments."""

    def test_connection(self):
        """Метод проверки подключения к api cloudpayments."""
        self.assertTrue(check_cloudpayments_connection())


class UnisenderFixtureMixin:
    """Фикстуры Unisender-тестов: Faker, mock-роутер, DI-контейнер."""

    def setUp(self):
        """Настраивает общие зависимости тестов Unisender."""
        super().setUp()

        self.fake = Faker()
        self.email = self.fake.email()
        self.list_id = self.fake.random_int(min=1)
        self.api_key = self.fake.sha256()
        self._override_settings(UNISENDER_API_KEY=self.api_key)

        self.router = MockRouter()
        client = zapros.Client(handler=MockMiddleware(self.router))
        container = dishka.make_container(context={zapros.Client: client})
        patcher = patch.object(di, "container", container)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(container.close)

    def _override_settings(self, **kwargs):
        overridden = self.settings(**kwargs)
        overridden.enable()
        self.addCleanup(overridden.disable)

    def _mock_post(self, url, response_data, status=HTTPStatus.OK):
        """Регистрирует в роутере ответ на POST по url, возвращает mock."""
        parsed = urlsplit(url)
        matcher = path(parsed.path).method("POST").host(parsed.hostname)
        mock = Mock.given(matcher).respond(
            zapros.Response(status=status, json=response_data)
        )
        self.router.add(mock)
        return mock

    def _assert_form(self, mock, expected):
        """Проверяет исходящий запрос: один раз, поля формы совпали."""
        mock.assert_called_once()
        self.assertEqual(
            self._form_fields(mock.calls[0]),
            {key: str(value) for key, value in expected.items()},
        )

    def _form_fields(self, request):
        """Тело запроса как плоский словарь полей формы."""
        body = request.body.decode("utf-8")
        fields = parse_qs(body, keep_blank_values=True)
        return {key: values[0] for key, values in fields.items()}


class UnisenderClientTest(UnisenderFixtureMixin, SimpleTestCase):
    """HTTP-клиент Unisender: сборка и отправка формы importContacts."""

    def setUp(self):
        """Настраивает тест клиента Unisender."""
        super().setUp()

        self.platform = self.fake.word()
        self.unisender = Client(
            api_key=self.api_key,
            platform=self.platform,
        )
        self.url = self.unisender._get_request_url("import_contacts")
        self.payload = {
            "field_names": ["email", "email_list_ids"],
            "data": [[self.email, self.list_id]],
            "overwrite_lists": 1,
        }
        self.expected_form = {
            "api_key": self.api_key,
            "platform": self.platform,
            "format": settings.DEFAULT_CONF["format"],
            "overwrite_lists": 1,
            **FIELD_NAMES,
            "data[0][0]": self.email,
            "data[0][1]": self.list_id,
        }
        self.import_mock = self._mock_post(self.url, {"result": {"total": 1}})

    def test_build_request_data_flattens_payload(self):
        """Вложенный payload разворачивается в плоские поля формы."""
        form = self.unisender._build_request_data(self.payload)

        self.assertEqual(form, self.expected_form)

    def test_api_request_posts_form_to_unisender(self):
        """_api_request отправляет форму в Unisender и возвращает ответ."""
        response = self.unisender._api_request(
            "import_contacts", self.payload
        )

        self.assertEqual(response.status, HTTPStatus.OK)
        self.assertEqual(response.json, {"result": {"total": 1}})
        self._assert_form(self.import_mock, self.expected_form)

    def test_api_request_raises_on_error_status(self):
        """Ненормативный статус Unisender приводит к StatusCodeError."""
        url = self.unisender._get_request_url("get_template")
        self._mock_post(
            url,
            {"error": "error", "code": 403},
            status=HTTPStatus.FORBIDDEN,
        )

        with self.assertRaises(zapros.StatusCodeError):
            self.unisender._api_request("get_template", {"template_id": 1})


class AdDonorTest(UnisenderFixtureMixin, TestCase):
    """ad_donor: донор сохраняется в БД и уходит в Unisender."""

    def setUp(self):
        """Настраивает зависимости теста."""
        super().setUp()

        self.subscription = settings.SUBSCRIPTION_CHOICES[0][0]
        self._override_settings(GROUPS={self.subscription: str(self.list_id)})
        self.expected_form = {
            "format": "json",
            "api_key": self.api_key,
            "overwrite_lists": 0,
            **FIELD_NAMES,
            "data[0][0]": self.email,
            "data[0][1]": self.list_id,
        }
        self.import_mock = self._mock_post(
            settings.IMPORT_UNISENDER,
            {"result": {"total": 1}},
        )

    def test_ad_donor_sends_donor_to_unisender(self):
        """ad_donor отправляет донора в importContacts."""
        ad_donor(self.email, self.subscription)

        self._assert_form(self.import_mock, self.expected_form)


class SendPaymentEmailTest(UnisenderFixtureMixin, SimpleTestCase):
    """send_payment_email: сначала getTemplate, затем sendEmail."""

    def setUp(self):
        """Настраивает зависимости теста."""
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
        self.template_form = {
            "format": "json",
            "api_key": self.api_key,
            "template_id": settings.TEMPLATE_ID,
        }
        self.email_form = {
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

    def test_send_payment_email_gets_template_and_sends_email(self):
        """Письмо отправляется по шаблону, полученному из Unisender."""
        send_payment_email(self.email, self.list_id)

        self._assert_form(self.template_mock, self.template_form)
        self._assert_form(self.email_mock, self.email_form)


class SendRequestTest(UnisenderFixtureMixin, SimpleTestCase):
    """send_request: запрос экспорта контактов (exportContacts)."""

    def setUp(self):
        """Настраивает зависимости теста."""
        super().setUp()

        self.response_data = {
            "result": {"task_uuid": self.fake.uuid4()},
        }
        self.expected_form = {
            "api_key": self.api_key,
            "notify_url": settings.NOTIFY_URL,
            "list_id": self.list_id,
            **FIELD_NAMES,
        }
        self.export_mock = self._mock_post(
            settings.EXPORT_UNISENDER,
            self.response_data,
        )

    def test_send_request_asks_unisender_to_export_contacts(self):
        """Запрос на экспорт уходит в Unisender, возвращается его ответ."""
        result = send_request(self.list_id)

        self.assertEqual(result, self.response_data)
        self._assert_form(self.export_mock, self.expected_form)
