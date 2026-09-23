"""Модуль тестов API."""

from http import HTTPMethod, HTTPStatus
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import dishka
import pytest
import zapros
from api.donor_service import ad_donor
from api.unisender_service import send_payment_email, send_request
from contacts.models import Donor
from django.conf import settings
from django.db import transaction
from django.test import SimpleTestCase
from donor_base import di
from donor_base.constants import SubscriptionStatuses
from donor_base.subscriptions import get_group_by_capitalized
from donor_base.unisender_client import Client
from faker import Faker
from zapros.matchers import path
from zapros.mock import Mock, MockMiddleware, MockRouter

CONTACT_FIELDS = ("email", "email_list_ids")

# Общие ключи полей запросов/ответов Unisender, вынесенные в константы,
# чтобы не плодить дублирующиеся строковые литералы (WPS226).
FORMAT_FIELD = "format"
API_KEY_FIELD = "api_key"
RESULT_FIELD = "result"


def expected_import_request_fields(
    email,
    list_id,
    api_key,
    overwrite_lists,
    format_,
    platform=None,
):
    """Возвращает ожидаемые поля запроса importContacts."""
    contact_values = [email, list_id]

    fields = {
        FORMAT_FIELD: format_,
        API_KEY_FIELD: api_key,
        "overwrite_lists": overwrite_lists,
    }

    if platform is not None:
        fields["platform"] = platform

    fields.update(
        {
            f"field_names[{index}]": field
            for index, field in enumerate(CONTACT_FIELDS)
        },
    )
    fields.update(
        {
            f"data[0][{index}]": contact_value
            for index, contact_value in enumerate(contact_values)
        },
    )

    return fields


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

    def _mock_request(self, method, url, response_data, status=HTTPStatus.OK):
        """Регистрирует в роутере ответ на запрос method по url."""
        parsed = urlsplit(url)
        matcher = path(parsed.path).method(method).host(parsed.hostname)
        mock = Mock.given(matcher).respond(
            zapros.Response(status=status, json=response_data),
        )
        self.router.add(mock)
        return mock

    def _assert_request_fields(self, mock, expected_fields):
        """Проверяет поля тела исходящего form-urlencoded запроса."""
        mock.assert_called_once()
        assert self._parse_request_fields(mock.calls[0]) == {
            key: str(field_value)
            for key, field_value in expected_fields.items()
        }

    def _assert_last_request_fields(self, mock, expected_fields):
        """
        Проверяет поля последнего исходящего запроса.

        Аналог _assert_request_fields для тестов с subTest.
        """
        assert mock.called
        assert self._parse_request_fields(mock.calls[-1]) == {
            key: str(field_value)
            for key, field_value in expected_fields.items()
        }

    def _parse_request_fields(self, request):
        """Разбирает поля тела исходящего form-urlencoded запроса."""
        body = request.body.decode("utf-8")
        fields = parse_qs(body, keep_blank_values=True)
        return {key: field_value[0] for key, field_value in fields.items()}


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
        self.payload = {
            "field_names": CONTACT_FIELDS,
            "data": [[self.email, self.list_id]],
            "overwrite_lists": 1,
        }
        self.expected_request_fields = expected_import_request_fields(
            email=self.email,
            list_id=self.list_id,
            api_key=self.api_key,
            overwrite_lists=1,
            format_=settings.DEFAULT_CONF[FORMAT_FIELD],
            platform=self.platform,
        )
        self.import_mock = self._mock_request(
            HTTPMethod.POST,
            # ruff: ignore[private-member-access]
            self.unisender._get_request_url("import_contacts"),
            {RESULT_FIELD: {"total": 1}},
        )

    def test_build_request_data_flattens_payload(self):
        """Вложенный payload разворачивается в плоские поля."""
        # ruff: ignore[private-member-access]
        request_fields = self.unisender._build_request_data(self.payload)

        assert request_fields == self.expected_request_fields

    def test_api_request_posts_form_to_unisender(self):
        """_api_request отправляет данные в Unisender и возвращает ответ."""
        # ruff: ignore[private-member-access]
        response = self.unisender._api_request("import_contacts", self.payload)

        assert response.status == HTTPStatus.OK
        assert response.json == {RESULT_FIELD: {"total": 1}}
        self._assert_request_fields(
            self.import_mock,
            self.expected_request_fields,
        )

    def test_api_request_raises_on_error_status(self):
        """Ненормативный статус Unisender приводит к StatusCodeError."""
        # ruff: ignore[private-member-access]
        url = self.unisender._get_request_url("get_template")
        self._mock_request(
            HTTPMethod.POST,
            url,
            {"error": "error", "code": 403},
            status=HTTPStatus.FORBIDDEN,
        )

        with pytest.raises(zapros.StatusCodeError):
            # ruff: ignore[private-member-access]
            self.unisender._api_request(
                "get_template",
                {"template_id": 1},
            )


@pytest.fixture
def ad_donor_data(db, faker):
    """Настраивает данные для проверки сохранения и workflow."""
    return faker.unique.email(), SubscriptionStatuses.ACTIVE.capitalized


@pytest.fixture
def sync_task():
    """Изолирует публикацию задачи отправки контактов."""
    with patch("api.donor_service.send_users_to_unisender") as task:
        yield task


@pytest.fixture
def email_task():
    """Изолирует создание задачи отправки письма."""
    with patch("api.donor_service.send_payment_email_task") as task:
        yield task


@pytest.fixture
def chain_factory():
    """Изолирует публикацию цепочки в брокер."""
    with patch("api.donor_service.chain") as factory:
        yield factory


def _rollback_donor_transaction(email, subscription):
    """Откатывает транзакцию БД после вызова ad_donor (для теста ошибки)."""
    with transaction.atomic():
        ad_donor(email, subscription, update=False)
        raise RuntimeError("rollback")


def test_ad_donor_saves_donor_and_publishes_task(
    ad_donor_data,
    sync_task,
    django_capture_on_commit_callbacks,
):
    """ad_donor сохраняет донора и публикует задачу после commit."""
    email, subscription = ad_donor_data

    with django_capture_on_commit_callbacks(execute=True):
        ad_donor(email, subscription, update=False)

    donor = Donor.objects.get(email=email)

    assert donor.subscription == subscription
    assert donor.count_declined == 0

    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=0,
    )
    signature = sync_task.si.return_value
    signature.apply_async.assert_called_once_with()


def test_ad_donor_uses_overwrite_lists_for_update(
    ad_donor_data,
    sync_task,
    django_capture_on_commit_callbacks,
):
    """При обновлении донора передаётся overwrite_lists=1."""
    email, subscription = ad_donor_data
    donor = Donor.objects.create(
        email=email,
        subscription=subscription,
        count_declined=2,
    )

    with django_capture_on_commit_callbacks(execute=True):
        ad_donor(
            email,
            subscription,
            update=True,
        )

    donor.refresh_from_db()

    assert donor.subscription == subscription
    assert donor.count_declined == 0

    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=1,
    )
    signature = sync_task.si.return_value
    signature.apply_async.assert_called_once_with()


def test_ad_donor_skips_task_before_commit(
    ad_donor_data,
    sync_task,
    django_capture_on_commit_callbacks,
):
    """Задача не публикуется до commit транзакции."""
    email, subscription = ad_donor_data
    signature = sync_task.si.return_value

    with django_capture_on_commit_callbacks(
        execute=False,
    ) as callbacks:
        ad_donor(email, subscription, update=False)

        signature.apply_async.assert_not_called()
        recorded_callbacks = list(callbacks)

    assert len(recorded_callbacks) == 1
    signature.apply_async.assert_not_called()

    recorded_callbacks[0]()

    signature.apply_async.assert_called_once_with()


def test_ad_donor_rolls_back_on_transaction_error(
    ad_donor_data,
    sync_task,
    django_capture_on_commit_callbacks,
):
    """При ошибке транзакции донор не сохраняется."""
    email, subscription = ad_donor_data

    with (
        pytest.raises(RuntimeError),
        django_capture_on_commit_callbacks(
            execute=True,
        ) as callbacks,
    ):
        _rollback_donor_transaction(email, subscription, update=False)

    assert not Donor.objects.filter(email=email).exists()
    assert callbacks == []
    sync_task.si.return_value.apply_async.assert_not_called()


def test_ad_donor_publishes_email_after_unisender(
    ad_donor_data,
    sync_task,
    email_task,
    chain_factory,
    django_capture_on_commit_callbacks,
):
    """Письмо публикуется после задачи отправки в Unisender."""
    email, subscription = ad_donor_data

    with django_capture_on_commit_callbacks(execute=True):
        ad_donor(
            email,
            subscription,
            update=False,
            send_email=True,
        )

        chain_factory.return_value.apply_async.assert_not_called()

    donor = Donor.objects.get(email=email)

    sync_task.si.assert_called_once_with(
        donor_ids=[donor.pk],
        overwrite_lists=0,
    )
    email_task.si.assert_called_once_with(
        email=email,
        list_id=get_group_by_capitalized(subscription),
    )

    sync_signature = sync_task.si.return_value
    email_signature = email_task.si.return_value

    chain_factory.assert_called_once_with(
        sync_signature,
        email_signature,
    )
    chain_factory.return_value.apply_async.assert_called_once_with()

    sync_signature.apply_async.assert_not_called()
    email_signature.apply_async.assert_not_called()


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
        self.template_request_fields = {
            FORMAT_FIELD: "json",
            API_KEY_FIELD: self.api_key,
            "template_id": settings.TEMPLATE_ID,
        }
        self.email_request_fields = {
            FORMAT_FIELD: "json",
            API_KEY_FIELD: self.api_key,
            "email": self.email,
            "sender_email": settings.DEFAULT_FROM_EMAIL,
            "sender_name": settings.UNISENDER_SENDER_NAME,
            "subject": self.template["subject"],
            "body": self.template["body"],
            "list_id": self.list_id,
        }
        self.template_mock = self._mock_request(
            HTTPMethod.POST,
            settings.URL_GET_TEMP,
            {RESULT_FIELD: self.template},
        )
        self.email_mock = self._mock_request(
            HTTPMethod.POST,
            settings.URL_SEND_EMAIL,
            {RESULT_FIELD: {"email_id": self.fake.random_int(min=1)}},
        )

    def test_sends_email_using_fetched_template(self):
        """Письмо отправляется по шаблону, полученному из Unisender."""
        send_payment_email(self.email, self.list_id)

        self._assert_request_fields(
            self.template_mock,
            self.template_request_fields,
        )
        self._assert_request_fields(
            self.email_mock,
            self.email_request_fields,
        )


class SendRequestTest(UnisenderFixtureMixin, SimpleTestCase):
    """send_request: запрос экспорта контактов (exportContacts)."""

    def setUp(self):
        """Настраивает зависимости теста."""
        super().setUp()

        self.response_data = {
            RESULT_FIELD: {"task_uuid": self.fake.uuid4()},
        }
        self.expected_request_fields = {
            API_KEY_FIELD: self.api_key,
            "notify_url": settings.NOTIFY_URL,
            "list_id": self.list_id,
            **{
                f"field_names[{index}]": field
                for index, field in enumerate(CONTACT_FIELDS)
            },
        }
        self.export_mock = self._mock_request(
            HTTPMethod.POST,
            settings.EXPORT_UNISENDER,
            self.response_data,
        )

    def test_exports_contacts_via_unisender(self):
        """Запрос на экспорт уходит в Unisender, возвращается его ответ."""
        extern_response_data = send_request(self.list_id)

        assert extern_response_data == self.response_data
        self._assert_request_fields(
            self.export_mock,
            self.expected_request_fields,
        )
