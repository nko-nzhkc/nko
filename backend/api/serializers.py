# Модуль сериализаторов API.
from rest_framework import serializers

from cloudpayments.models import CloudPayment
from forbiddenwords.models import ForbiddenWord


class ForbiddenwordSerializer(serializers.ModelSerializer):
    """Сериализатор запрещенных слов."""

    class Meta:
        model = ForbiddenWord
        fields = ("forbidden_word",)


class CloudpaymentsSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели CloudPayment.
    """

    class Meta:
        model = CloudPayment
        fields = (
            "id",
            "email",
            "donat",
            "custom_donat",
            "payment_method",
            "monthly_donat",
            "subscription",
            "status",
            "currency",
            "user_account_id",
            "date_created",
            "date_processed",
        )
