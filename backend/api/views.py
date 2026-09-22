# Модуль представлений проекта.
from cloudpayments.models import CloudPayment
from contacts.models import Contact
from django.http import JsonResponse
from django.views import View
from donor_base.constants import HTTPMethod
from forbiddenwords.models import ForbiddenWord
from mixplat.models import MixPlat
from rest_framework import status, viewsets
from rest_framework.decorators import action
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


class ContactViewSet(viewsets.ModelViewSet):
    """Вьюсет контактов."""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

    @action(
        detail=False,
        url_path="start",
        methods=(HTTPMethod.POST.value,),
    )
    def start(self, request):
        """Запуск процесса получения контактов из Unisender."""
        return Response(
            send_request(request.data["list_id"]),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        url_path="get_contacts",
        methods=(HTTPMethod.GET.value, HTTPMethod.POST.value),
    )
    def get_contacts(self, request):
        """Метод получения контактов от Unisender."""
        if request.method == "get":
            return Response(status=status.HTTP_200_OK)
        return Response(
            {
                "result": add_contacts(
                    request.data["result"]["file_to_download"],
                ),
            },
            status=status.HTTP_200_OK,
        )


class ForbiddenwordViewSet(ViewListCreateMixinsSet):
    """Вьюсет запрещенных слов."""

    queryset = ForbiddenWord.objects.all()
    serializer_class = ForbiddenwordSerializer
    pagination_class = None


class MixplatViewSet(viewsets.ModelViewSet):
    """Вьюсет Mixplat."""

    queryset = MixPlat.objects.all()
    serializer_class = MixPlatSerializer

    @action(
        detail=False,
        url_path="payment_status",
        methods=(HTTPMethod.POST.value,),
    )
    def payment_status(self, request):
        """Метод получения данных от Mixplat."""
        return mixplat_request_handler(request)


class CloudPaymentsViewSet(viewsets.GenericViewSet):
    """Вьюсет для Cloudpayment."""

    @action(
        detail=False,
        url_path="create_cloudpayment",
        methods=(HTTPMethod.POST.value,),
    )
    def create_cloudpayment(self, request):
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

    def get(self, request, *args, **kwargs):
        """Обрабатывает GET-запрос для получения списка всех платежей."""
        mixplat_payments = MixPlat.objects.all()
        cloudpayment_payments = CloudPayment.objects.all()

        all_payments_list = mixplat_payments.union(cloudpayment_payments)
        all_payments_list = all_payments_list.order_by("-pub_date")

        payments_data = list(all_payments_list.values())

        return JsonResponse({"payments_list": payments_data})
