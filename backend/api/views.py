# Модуль представлений проекта.
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .mixins import ViewListCreateMixinsSet
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


class ContactViewSet(viewsets.GenericViewSet):
    """Вьюсет контактов."""

    @action(detail=False, url_path="start", methods=("post",))
    def start(self, request):
        """Запуск процесса получения контактов из Unisender."""
        return Response(
            send_request(request.data["list_id"]),
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        url_path="get_contacts",
        methods=(
            "get",
            "post",
        ),
    )
    def get_contacts(self, request):
        """Метод получения контактов от Unisender."""
        if request.method == "GET":
            return Response(status=status.HTTP_200_OK)
        return Response(
            dict(
                result=add_contacts(request.data["result"]["file_to_download"])
            ),
            status=status.HTTP_200_OK,
        )


class ForbiddenwordViewSet(ViewListCreateMixinsSet):
    """Вьюсет запрещенных слов."""

    queryset = ForbiddenWord.objects.all()
    serializer_class = ForbiddenwordSerializer
    permission_classes = [IsAdmin]
    pagination_class = None


class MixplatViewSet(viewsets.GenericViewSet):
    """Вьюсет Mixplat."""

    @action(detail=False, url_path="payment_status", methods=("post",))
    def payment_status(self, request):
        """Метод получения данных от Mixplat."""
        return mixplat_request_handler(request)


class CloudPaymentsViewSet(viewsets.GenericViewSet):
    """Вьюсет для Cloudpayment."""

    @action(detail=False, url_path="create_cloudpayment", methods=["post"])
    def create_cloudpayment(self, request):
        """Создание экземпляра Cloudpayment."""
        serializer = CloudpaymentsSerializer(
            data=handling_cloudpayment_data(request)
        )
        if serializer.is_valid():
            serializer.save()
            return Response(dict(code=0), status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentsListViewSet(viewsets.GenericViewSet):
    """Список всех платежей (Mixplat + CloudPayments)."""

    def list(self, request, *args, **kwargs):
        payments = (
            MixPlat.objects.all()
            .union(CloudPayment.objects.all())
            .order_by("-pub_date")
        )
        return Response({"payments_list": list(payments.values())})
