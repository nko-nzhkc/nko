# Модуль представлений проекта.
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .mixins import ViewListCreateMixinsSet
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


class ContactViewSet(viewsets.GenericViewSet):
    """Вьюсет контактов."""

    @action(detail=False, url_path="start", methods=("post",))
    def start(self, request):
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
            data=handling_cloudpayment_data(request),
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"code": 0}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentsListViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Список всех платежей (Mixplat + CloudPayments)."""

    serializer_class = CloudpaymentsSerializer

    def get_queryset(self):
        return (
            MixPlat.objects.all()
            .union(CloudPayment.objects.all())
            .order_by("-pub_date")
        )
