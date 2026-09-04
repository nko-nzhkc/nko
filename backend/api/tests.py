"""Модуль тестов API."""

import urllib.parse
from contextlib import contextmanager

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from zapros import Response
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter, mock_http

from donor_base.unisender_client import Client

from .utils import (ad_donor, check_cloudpayments_connection,
                    send_payment_email, send_request)


@contextmanager
def mock_unisender_http():
    """Перехватывает HTTP-запросы zapros и отдаёт MockRouter.

    Код проекта сам создаёт zapros.Client() внутри функций, поэтому
    внедрить handler напрямую нельзя. mock_http подменяет стандартный
    сетевой handler zapros (StdNetworkHandler.handle), а MockMiddleware
    маршрутизирует запросы в MockRouter, который отвечает только
    зарегистрированными Mock-ами (несовпавший запрос -> ValueError).
    """
    router = MockRouter()
    with mock_http(MockMiddleware(router=router)):
        yield router


class CloudpaymentsConnectionTest(TestCase):
    """Тест-кейс проверки подключения к api cloudpayments."""

    def test_connection(self):
        """Метод проверки подключения к api cloudpayments."""
        self.assertTrue(check_cloudpayments_connection())


class UnisenderClientTest(SimpleTestCase):
    """Тесты donor_base.unisender_client.Client — issue #104."""

    def test_api_request_posts_form_to_unisender(self):
        """POST через zapros: правильный URL, form-urlencoded и int -> str."""
        client = Client(api_key="test-api-key", platform="donor_base")
        data = {
            "field_names": ["email", "email_list_ids"],
            "data": [["donor@example.com", "5"]],
            "overwrite_lists": 1,
        }
        mock = (
            Mock.given(
                path("/en/api/importContacts")
                .method("POST")
                .host("api.unisender.com")
            )
            .respond(Response(status=200, json={"result": {"total": 1}}))
            .once()
        )

        with mock_unisender_http() as router:
            router.add(mock)
            response = client._api_request("import_contacts", data)

            self.assertEqual(response.status, 200)
            self.assertEqual(response.json, {"result": {"total": 1}})

            request = mock.calls[0]
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.hostname, "api.unisender.com")
            self.assertEqual(request.url.pathname, "/en/api/importContacts")

            form = urllib.parse.parse_qs(request.body.decode("utf-8"))
            self.assertEqual(form["overwrite_lists"], ["1"])
            self.assertEqual(form["field_names[0]"], ["email"])
            self.assertEqual(form["data[0][0]"], ["donor@example.com"])
            self.assertEqual(form["data[0][1]"], ["5"])


@override_settings(UNISENDER_API_KEY="test-api-key")
class AdDonorTest(TestCase):
    """Тест api.utils.ad_donor -> Unisender importContacts."""

    def test_ad_donor_posts_to_import_contacts(self):
        """POST на importContacts: URL, form-urlencoded и int -> str."""
        mock = (
            Mock.given(
                path("/ru/api/importContacts")
                .method("POST")
                .host("api.unisender.com")
            )
            .respond(Response(status=200, json={"result": {"total": 1}}))
            .once()
        )

        with mock_unisender_http() as router:
            router.add(mock)
            ad_donor("donor@example.com", "Active")

            request = mock.calls[0]
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.pathname, "/ru/api/importContacts")

            form = urllib.parse.parse_qs(request.body.decode("utf-8"))
            self.assertEqual(form["overwrite_lists"], ["0"])
            self.assertEqual(form["field_names[0]"], ["email"])
            self.assertEqual(form["field_names[1]"], ["email_list_ids"])
            self.assertEqual(form["data[0][0]"], ["donor@example.com"])
            self.assertEqual(form["data[0][1]"], [settings.GROUPS["Active"]])


@override_settings(
    UNISENDER_API_KEY="test-api-key",
    TEMPLATE_ID="123",
    DEFAULT_FROM_EMAIL="sender@example.com",
)
class SendPaymentEmailTest(SimpleTestCase):
    """Тест api.utils.send_payment_email -> getTemplate + sendEmail."""

    def test_send_payment_email_calls_get_template_and_send_email(self):
        """Два POST: getTemplate, затем sendEmail с подставленным шаблоном."""
        get_template_mock = (
            Mock.given(path("/ru/api/getTemplate").method("POST"))
            .respond(
                Response(
                    status=200,
                    json={
                        "result": {
                            "subject": "Welcome",
                            "body": "Hello",
                        }
                    },
                )
            )
            .once()
        )
        send_email_mock = (
            Mock.given(path("/ru/api/sendEmail").method("POST"))
            .respond(Response(status=200, json={"result": {"email_id": 42}}))
            .once()
        )

        with mock_unisender_http() as router:
            router.add(get_template_mock)
            router.add(send_email_mock)
            send_payment_email("donor@example.com", "5")

            gt = get_template_mock.calls[0]
            self.assertEqual(gt.url.pathname, "/ru/api/getTemplate")
            gt_form = urllib.parse.parse_qs(gt.body.decode("utf-8"))
            self.assertEqual(gt_form["template_id"], ["123"])

            se = send_email_mock.calls[0]
            self.assertEqual(se.url.pathname, "/ru/api/sendEmail")
            se_form = urllib.parse.parse_qs(se.body.decode("utf-8"))
            self.assertEqual(se_form["email"], ["donor@example.com"])
            self.assertEqual(se_form["subject"], ["Welcome"])
            self.assertEqual(se_form["body"], ["Hello"])
            self.assertEqual(se_form["list_id"], ["5"])


@override_settings(UNISENDER_API_KEY="test-api-key")
class SendRequestTest(SimpleTestCase):
    """Тест api.utils.send_request -> Unisender exportContacts."""

    def test_send_request_posts_to_export_contacts(self):
        """POST на exportContacts: URL, form-urlencoded, .json (property)."""
        mock = (
            Mock.given(path("/ru/api/async/exportContacts").method("POST"))
            .respond(
                Response(status=200, json={"result": {"task_uuid": "abc"}})
            )
            .once()
        )

        with mock_unisender_http() as router:
            router.add(mock)
            result = send_request("5")

            self.assertEqual(result, {"result": {"task_uuid": "abc"}})

            request = mock.calls[0]
            self.assertEqual(
                request.url.pathname, "/ru/api/async/exportContacts"
            )

            form = urllib.parse.parse_qs(request.body.decode("utf-8"))
            self.assertEqual(form["list_id"], ["5"])
            self.assertEqual(form["field_names[0]"], ["email"])
            self.assertEqual(form["field_names[1]"], ["email_list_ids"])
