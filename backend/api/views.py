# Модуль представлений проекта.
from http import HTTPMethod
from typing import Any

from cloudpayments.models import CloudPayment
from contacts.models import Contact
from django.http import HttpRequest, JsonResponse
from django.views import View
from forbiddenwords.models import ForbiddenWord
from mixplat.models import MixPlat
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from api.cloudpayments_service import handling_cloudpayment_data
from api.mixins import ViewListCreateMixinsSet
from api.mixplat_service import mixplat_request_handler
from api.serializers import (
    CloudpaymentsSerializer,
    ContactSerializer,
    ForbiddenwordSerializer,
    MixPlatSerializer,
)
from api.unisender_service import add_contacts, send_request


def _form_error_response() -> Response:
    return Response(
        {"error": "Invalid payload"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


class ContactViewSet(viewsets.ModelViewSet[Contact]):
    """Вьюсет контактов."""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    @action(
        detail=False,
        url_path="start",
        methods=(HTTPMethod.POST.value,),
    )
    def start(self, request: Request) -> Response:
        """Запуск процесса получения контактов из Unisender."""
        data = request.data
        if not isinstance(data, dict):
            return _form_error_response()
        list_id = data.get("list_id")
        if not list_id:
            return _form_error_response()
        return Response(
            send_request(list_id),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        url_path="get_contacts",
        methods=(HTTPMethod.GET.value, HTTPMethod.POST.value),
    )
    def get_contacts(self, request: Request) -> Response:
        """Метод получения контактов от Unisender."""
        if request.method == "GET":
            return Response(status=status.HTTP_200_OK)
        data = request.data
        if not isinstance(data, dict):
            return _form_error_response()
        file_result = data.get("result")
        file_url = (
            file_result.get("file_to_download")
            if isinstance(file_result, dict)
            else None
        )
        if not file_url:
            return _form_error_response()
        return Response(
            {"result": add_contacts(file_url)},
            status=status.HTTP_200_OK,
        )


class ForbiddenwordViewSet(ViewListCreateMixinsSet[ForbiddenWord]):
    """Вьюсет запрещенных слов."""

    queryset = ForbiddenWord.objects.all()
    serializer_class = ForbiddenwordSerializer
    pagination_class = None


class MixplatViewSet(viewsets.ModelViewSet[Any]):
    """Вьюсет Mixplat."""

    queryset = MixPlat.objects.all()
    serializer_class = MixPlatSerializer

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
        methods=(HTTPMethod.POST.value,),
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


class PaymentsListView(View):
    """Вью для всех платежей."""

    model = None

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        """Обрабатывает GET-запрос для получения списка всех платежей."""
        mixplat_payments = MixPlat.objects.all()
        cloudpayment_payments = CloudPayment.objects.all()

        all_payments_list = mixplat_payments.union(cloudpayment_payments)
        all_payments_list = all_payments_list.order_by("-pub_date")

        payments_data = list(all_payments_list.values())

        return JsonResponse({"payments_list": payments_data})
