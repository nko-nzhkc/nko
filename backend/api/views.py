# Модуль представлений проекта.
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdmin
from .serializers import (
    ForbiddenwordSerializer,
    CloudpaymentsSerializer,
)
from .utils import (
    add_contacts,
    handling_cloudpayment_data,
    mixplat_request_handler,
    send_request,
)
from forbiddenwords.models import ForbiddenWord
from mixplat.models import MixPlat
from cloudpayments.models import CloudPayment


class StartContactSendView(APIView):
    """Запуск процесса получения контактов из Unisender."""

    def post(self, request):
        return Response(
            send_request(request.data["list_id"]),
            status=status.HTTP_200_OK,
        )


class GetContactsView(APIView):
    """Получение контактов от Unisender."""

    def get(self, request):
        return Response(status=status.HTTP_200_OK)

    def post(self, request):
        return Response(
            dict(
                result=add_contacts(request.data["result"]["file_to_download"])
            ),
            status=status.HTTP_200_OK,
        )


class ForbiddenWordListView(ListCreateAPIView):
    """Список запрещённых слов и создание нового."""

    queryset = ForbiddenWord.objects.all()
    serializer_class = ForbiddenwordSerializer
    permission_classes = [IsAdmin]
    pagination_class = None


class MixplatView(APIView):
    """Получение данных от Mixplat."""

    def post(self, request):
        return mixplat_request_handler(request)


class CloudPaymentCreateView(APIView):
    """
    Создание экземпляра Cloudpayment.
    """

    def post(self, request):
        serializer = CloudpaymentsSerializer(
            data=handling_cloudpayment_data(request)
        )
        if serializer.is_valid():
            serializer.save()
            return Response(dict(code=0), status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentsListView(APIView):
    """
    API-представление для получения объединённого списка платежей.
    """

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        mixplat_payments = MixPlat.objects.all()
        cloudpayment_payments = CloudPayment.objects.all()

        all_payments_list = mixplat_payments.union(cloudpayment_payments)
        all_payments_list = all_payments_list.order_by("-pub_date")

        payments_data = list(all_payments_list.values())

        return Response(
            {"payments_list": payments_data},
            status=status.HTTP_200_OK,
        )
