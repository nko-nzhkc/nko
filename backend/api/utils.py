# Модуль бизнес логики проекта.
import base64
import csv
import http
import requests
import os
import shutil
from datetime import datetime

from django.conf import settings
from django.utils.timezone import make_aware
from rest_framework import status
from rest_framework.response import Response

from contacts.models import Donor
from mixplat.models import MixPlat


def string_to_date(value):
    """Метод преобразования строки в дату, установка time-zone."""
    return make_aware(datetime.strptime(value, settings.DATE_FORMAT))


def donor_exists(email):
    """Метод проверки наличия контакта донора в ДБ."""
    return Donor.objects.filter(email=email).exists()


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

        MixPlat.objects.create(**mixplat_obj_dict)

        if request.data.get("recurrent_id") is not None:
            Donor.objects.update_or_create(
                email=request.data["user_email"],
                subcsription="Active",
            )
        else:
            Donor.objects.update_or_create(
                email=request.data["user_email"],
                subcsription="Inactive",
            )

        return Response(dict(result="ok"), status=status.HTTP_200_OK)
    except KeyError:
        return Response(
            dict(result="error", error_description="Internal error"),
            status=status.HTTP_400_BAD_REQUEST,
        )


def check_donor_subscriptions(email):
    """Проверка наличия подписки у донора."""
    url = settings.CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL
    username = settings.CLOUDPAYMENTS_PUBLIC_ID
    password = settings.CLOUDPAYMENTS_API_SECRET
    basic_encoded = base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {basic_encoded}"}
    body = {"accountId": f"{email}"}
    response = requests.post(url, headers=headers, json=body)
    if response.json()["Model"]:
        return settings.SUBSCRIPTION_CHOICES[0][0]
    return settings.SUBSCRIPTION_CHOICES[1][0]


def handling_cloudpayment_data(request):
    """Формирование данных для сериалайзера CloudpaymentsSerializer."""
    # Предлполагаем, что request.data содержит json-объект,
    # т.е. ответ сервиса Cloudpayments при запросе на создании платежа.
    if isinstance(request.data, dict) and "Model" in request.data:
        model = request.data["Model"][0]
        data = {
            "email": model.get("Email"),
            "donat": model.get("Amount"),
            "date_created": model.get("CreatedDateIso"),
            "date_processed": model.get("ConfirmDateIso"),
            "payment_id": model.get("TransactionId"),
            "status": model.get("Status"),
            "payment_operator": "Cloudpayment",
            "payment_method": model.get("CardType"),
            "user_account_id": model.get("TransactionId"),
            "currency": model.get("Currency"),
        }
        subscription = check_donor_subscriptions(data["email"])
        Donor.objects.update_or_create(
            email=data["email"], subcsription=subscription
        )
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


def send_payment_email(email, message):
    """Sending message via Unisender method."""
    url = settings.DEFAULT_CONF["base_url"] + "/ru/api/sendEmail?format=json"

    data = {
        "api_key": settings.DEFAULT_CONF["api_key"],
        "format": "json",
        "email": email,
        "sender_email": settings.DEFAULT_FROM_EMAIL,
        "sender_name": settings.UNISENDER_SENDER_NAME,
        "subject": "Payment information",
        "body": message,
        "list_id": 1,
    }
    response = requests.post(url, data=data)

    if response.status_code != status.HTTP_200_OK:
        print(f"Ошибка при отправке сообщения: {response.status_code}")
        print(f"Ответ сервера: {response.text}")
    else:
        response_data = response.json()
        if "error" in response_data:
            print("Ошибка при отправке сообщения:")
            print(f"Код ошибки: {response_data['code']}")
            print(f"Сообщение об ошибке: {response_data['error']}")
        elif "result" in response_data:
            print("Сообщение успешно отправлено!")
            print(f"Email ID: {response_data['result']['email_id']}")
        else:
            print(f"Неизвестный ответ от сервера: {response_data}")


def send_request():
    """Отправка запроса на получение контактов доноров от Unisender."""
    response = requests.get(settings.REQUEST_URL)
    if response.status_code != status.HTTP_200_OK:
        raise f"Ошибка при запросе: {response.status_code}"
    return response.json()["result"]["task_uuid"]


def add_contacts(file_url):
    """Добавление доноров в БД из файла, получаемого по ссылке."""
    response = requests.get(file_url)
    if response.status_code == status.HTTP_200_OK:
        bulk_list = list()
        directory = "files"
        if not os.path.exists(directory):
            os.makedirs(directory)
        file_path = os.path.join(directory, "data.csv")

        with open(file_path, "wb") as file:
            file.write(response.content)

        with open(file_path, encoding="utf-8") as csv_file:
            file_reader = csv.reader(csv_file, delimiter=",")
            for row in file_reader:
                if row[0] != "email" and donor_exists(row[0]) is False:
                    bulk_list.append(Donor(email=row[0]))
            Donor.objects.bulk_create(bulk_list)

        try:
            shutil.rmtree(directory)  # удаляем папку с файлом
        except OSError as e:
            raise f"Error: {e.filename, e.strerror}"

        return f"Добавленно {len(bulk_list)} контактов."
    return f"Файл по ссылке не получен, код ответа {response.status_code}."
