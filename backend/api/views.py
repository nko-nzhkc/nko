# Модуль представлений проекта.
from http import HTTPMethod

from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.cloudpayments_service import handling_cloudpayment_data
from api.mixins import ViewListCreateMixinsSet
from api.mixplat_service import mixplat_request_handler
from api.serializers import (
    CloudpaymentsSerializer,
    ForbiddenwordSerializer,
)
from api.unisender_service import add_contacts, send_request
from cloudpayments.models import CloudPayment
from contacts.models import Contact
from forbiddenwords.models import ForbiddenWord
from mixplat.models import MixPlat


class ContactViewSet(viewsets.GenericViewSet[Contact]):
    """Вьюсет контактов."""

    @action(detail=False, url_path="start", methods=(HTTPMethod.POST.value,))
    def start(self, request: Request) -> Response:
        """Запуск процесса получения контактов из Unisender."""
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": "Expected an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            send_request(data["list_id"]),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        url_path="get_contacts",
        methods=(
            HTTPMethod.GET.value,
            HTTPMethod.POST.value,
        ),
    )
    def get_contacts(self, request: Request) -> Response:
        """Метод получения контактов от Unisender."""
        if request.method == "GET":
            return Response(status=status.HTTP_200_OK)
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"detail": "Expected an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "result": add_contacts(
                    data["result"]["file_to_download"],
                ),
            },
            status=status.HTTP_200_OK,
        )


class ForbiddenwordViewSet(ViewListCreateMixinsSet[ForbiddenWord]):
    """Вьюсет запрещенных слов."""

    queryset = ForbiddenWord.objects.all()
    serializer_class = ForbiddenwordSerializer
    pagination_class = None


class MixplatViewSet(viewsets.GenericViewSet[MixPlat]):
    """Вьюсет Mixplat."""

    @action(
        detail=False,
        url_path="payment_status",
        methods=(HTTPMethod.POST.value,),
    )
    def payment_status(self, request: Request) -> Response:
        """Метод получения данных от Mixplat."""
        return mixplat_request_handler(request)


class CloudPaymentsViewSet(viewsets.GenericViewSet[CloudPayment]):
    """Вьюсет для Cloudpayment."""

    @action(
        detail=False,
        url_path="create_cloudpayment",
        methods=[HTTPMethod.POST.value],
    )
    def create_cloudpayment(self, request: Request) -> Response:
        """Создание экземпляра Cloudpayment."""
        serializer = CloudpaymentsSerializer(
            data=handling_cloudpayment_data(request),
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"code": 0}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentsListViewSet(
    mixins.ListModelMixin,
    viewsets.GenericViewSet[CloudPayment],
):
    """Список всех платежей (Mixplat + CloudPayments)."""

    serializer_class = CloudpaymentsSerializer

    def get_queryset(self) -> QuerySet[CloudPayment]:
        """Объединённый список платежей Mixplat и CloudPayments."""
        return (
            CloudPayment.objects.all()
            .union(MixPlat.objects.all())
            .order_by("-pub_date")
        )
