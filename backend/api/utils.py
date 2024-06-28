# Модуль бизнес логики проекта.
import http
import requests
from datetime import datetime

from django.conf import settings
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from contacts.models import Contact
from mixplat.models import MixPlat


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return make_aware(datetime.strptime(value, settings.DATE_FORMAT))


def mixplat_request_handler(request):
    """Метод создания объектов из данных от Mixplat."""
    try:
        mixplat_obj_dict = dict(
            email=request.data["user_email"],
            donat=request.data["amount"],
            custom_donat=request.data["amount_user"],
            payment_method=request.data["payment_method"],
            payment_id=request.data["payment_id"],
            status=request.data["status"],
            user_account_id=request.data["user_account_id"],
            date_created=string_to_date(request.data["date_created"]),
            date_processed=string_to_date(request.data["date_processed"]),
            payment_operator="mixplat",
            currency=request.data["currency"],
        )
        contact_obj_dict = dict(
            username=request.data["user_name"],
            email=request.data["user_email"],
            subject=request.data["user_account_id"],
            comment=request.data["user_comment"],
        )
        MixPlat.objects.create(**mixplat_obj_dict)
        if (
            Contact.objects.filter(
                username=request.data["user_name"],
                email=request.data["user_email"],
            ).exists()
            is False
        ):
            Contact.objects.create(**contact_obj_dict)

        return Response(dict(result="ok"), status=status.HTTP_200_OK)
    except KeyError:
        return Response(
            dict(result="error", error_description="Internal error"),
            status=status.HTTP_400_BAD_REQUEST,
        )


def get_cloudpayment_data(request):
    """Формирование данных для сериалайзера CloudpaymentsSerializer."""
    # Предлполагаем, что request.data содержит json-объект,
    # т.е. ответ сервиса Cloudpayments при запросе на создании платежа.
    if isinstance(request.data, dict) and "Model" in request.data:
        model = request.data["Model"][0]
        data = {
            "email": model.get("Email"),
            "custom_donat": model.get("Amount"),
            "date_created": model.get("CreatedDateIso"),
            "date_processed": model.get("ConfirmDateIso"),
            "payment_id": model.get("TransactionId"),
            "status": model.get("Status"),
            "payments_operator": model.get("Issuer"),
            "payment_method": model.get("CardType"),
            "user_account_id": model.get("TransactionId"),
            "currency": model.get("Currency"),
        }
        return data
    raise ValueError("Неправильная структура request.data")


def check_cloudpayments_connection():
    """Проверка подключения к api cloudpayments."""
    url = settings.CLOUDPAYMENTS_API_TEST_URL
    headers = {"Content-Type": "application/json"}
    auth = (
        settings.CLOUDPAYMENTS_PUBLIC_ID,
        settings.CLOUDPAYMENTS_API_SECRET,
    )
    response = requests.post(url, headers=headers, auth=auth)
    if response.status_code == http.HTTPStatus.OK:
        return True
    return False
