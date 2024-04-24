import requests
from django.conf import settings


def send_email(recipient_email, subject, message):
    sender_email = settings.DEFAULT_FROM_EMAIL
    sender_name = "Vasya Pupkin"
    api_key = ""  # ключ можно скопировать в личном кабинете Unisender
    # dummy. list_id можно получить в аккаунте Unisender (вроде как)
    list_id = 1

    url = "https://api.unisender.com/ru/api/sendEmail"

    data = {
        "api_key": api_key,
        "format": "json",
        "email": recipient_email,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "subject": subject,
        "body": message,
        "list_id": list_id,
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        print(f"Ошибка при отправке сообщения: {response.status_code}")
    else:
        print("Сообщение успешно отправлено!")
