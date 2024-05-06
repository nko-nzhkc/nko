import requests
from django.conf import settings


def send_failed_payment_email(recipient_email, message):
    sender_email = settings.DEFAULT_FROM_EMAIL
    subject = "Payment Rejected"
    api_key = ""

    url = "https://api.unisender.com/ru/api/sendEmail"

    data = {
        "api_key": api_key,
        "format": "json",
        "email": recipient_email,
        "sender_email": sender_email,
        "subject": subject,
        "body": message,
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        print(f"Ошибка при отправке сообщения: {response.status_code}")
    else:
        print("Сообщение успешно отправлено")
