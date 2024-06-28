# Модуль сериализаторов API.
from rest_framework import serializers

from contacts.models import Contact
from forbiddenwords.models import ForbiddenWord
from cloudpayments.models import CloudPayment
from mixplat.models import MixPlat


class MixPlatSerializer(serializers.ModelSerializer):
    """Сериализатор платежа Mixplat."""

    class Meta:
        model = MixPlat
        fields = (
            "id",
            "email",
            "donat",
            "custom_donat",
            "payment_method",
            "monthly_donat",
            "subscription",
            "payment_id",
            "status",
            "user_account_id",
            "user_comment",
            "date_created",
            "date_processed",
        )


class ContactSerializer(serializers.ModelSerializer):
    """Сериализатор контактов."""

    class Meta:
        model = Contact
        fields = ("username", "email", "subject", "comment")


class ForbiddenwordSerializer(serializers.ModelSerializer):
    """Сериализатор запрещенных слов."""

    class Meta:
        model = ForbiddenWord
        fields = ("forbidden_word",)


class CloudpaymentsSerializer(serializers.ModelSerializer):
    """
    Сериалайзер для модели CloudPayment.
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
