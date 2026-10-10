import logging
from typing import Any

from django.conf import settings

from donor_base import http_client


logger = logging.getLogger(__name__)


def _extract_unisender_result(
    response_data: dict[str, Any],
    error_label: str = "Ошибка:",
) -> Any | None:
    """Извлекает result из ответа Unisender."""
    if "error" in response_data:
        logger.info(error_label)
        logger.info("Код ошибки: %s", response_data.get("code"))
        logger.info("Сообщение об ошибке: %s", response_data.get("error"))
        return None
    unisender_result = response_data.get("result")
    if unisender_result is not None:
        return unisender_result
    logger.info("Неизвестный ответ от сервера: %s", response_data)
    return None


def send_payment_email(email: str, list_id: int | str) -> None:
    """Получение шаблона и отправка письма донору."""
    template_data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "template_id": settings.TEMPLATE_ID,
    }
    response = http_client.post_form(settings.URL_GET_TEMP, template_data)
    template = _extract_unisender_result(
        response.json,
        "Ошибка при запросе шаблона:",
    )
    if template is None:
        return
    data = {
        "format": "json",
        "api_key": settings.UNISENDER_API_KEY,
        "email": email,
        "sender_email": settings.DEFAULT_FROM_EMAIL,
        "sender_name": settings.UNISENDER_SENDER_NAME,
        "subject": template["subject"],
        "body": template["body"],
        "list_id": list_id,
    }
    response = http_client.post_form(settings.URL_SEND_EMAIL, data)
    unisender_result = _extract_unisender_result(
        response.json,
        "Ошибка при отправке сообщения:",
    )
    if unisender_result is not None:
        logger.info("Сообщение успешно отправлено!")
        logger.info("Email ID: %s", unisender_result["email_id"])


def send_request(list_id: int | str) -> dict[str, Any] | None:
    """Отправка запроса на получение контактов доноров от Unisender."""
    data = {
        "api_key": settings.UNISENDER_API_KEY,
        "notify_url": settings.NOTIFY_URL,
        "field_names[0]": "email",
        "field_names[1]": "email_list_ids",
        "list_id": list_id,
    }
    response = http_client.post_form(settings.EXPORT_UNISENDER, data)
    response_data: dict[str, Any] = response.json
    unisender_result = _extract_unisender_result(response_data)
    if unisender_result is None:
        return None
    logger.info("Успешно!")
    logger.info("result: %s", unisender_result)
    return response_data