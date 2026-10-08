"""Тесты webhook Mixplat и проверки его payload."""

from typing import Any

import pytest
from django.utils import timezone
from rest_framework import status

from contacts.models import Donor
from donor_base.constants import DATE_FORMAT, SubscriptionStatuses
from mixplat.models import MixPlat


def test_string_to_date_returns_aware_datetime() -> None:
    """Строковая дата преобразуется в timezone-aware datetime."""
    from api.mixplat_service import string_to_date

    value = "2024-01-02 03:04:05"
    result = string_to_date(value)

    assert timezone.is_aware(result)
    assert result.strftime(DATE_FORMAT) == value


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("recurrent_id", "expected_subscription"),
    [
        ("recurrent-1", SubscriptionStatuses.ACTIVE.capitalized),
        (None, SubscriptionStatuses.INACTIVE.capitalized),
    ],
)
def test_mixplat_webhook_saves_payment_and_donor(
    recurrent_id: str | None,
    expected_subscription: str,
    mixplat_payload: dict[str, str | None],
    api_client: Any,
    donor_workflow: Any,
    django_capture_on_commit_callbacks: Any,
) -> None:
    """Webhook action сохраняет платёж и обновляет реального донора."""
    mixplat_payload["recurrent_id"] = recurrent_id

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            "/api/mixplat/payment_status/",
            data=mixplat_payload,
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"result": "ok"}

    email = mixplat_payload["user_email"]
    payment = MixPlat.objects.get(email=email)
    donor = Donor.objects.get(email=email)

    assert payment.donat == 100
    assert payment.custom_donat == 150
    assert payment.payment_operator == "mixplat"
    assert donor.subscription == expected_subscription


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalid_case",
    [
        "non_object",
        "missing_required_field",
        "non_string_required_field",
        "non_string_recurrent_id",
    ],
)
def test_mixplat_webhook_rejects_invalid_payload(
    invalid_case: str,
    mixplat_payload: dict[str, str | None],
    api_client: Any,
) -> None:
    """Не-object payload, пропущенное поле и неверные типы дают 400."""
    payload: Any = dict(mixplat_payload)

    if invalid_case == "non_object":
        payload = []
    elif invalid_case == "missing_required_field":
        payload.pop("payment_id")
    elif invalid_case == "non_string_required_field":
        payload["amount"] = 100
    else:
        payload["recurrent_id"] = 123

    response = api_client.post(
        "/api/mixplat/payment_status/",
        data=payload,
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "result": "error",
        "error_description": "Internal error",
    }
    assert not MixPlat.objects.exists()
    assert not Donor.objects.exists()
