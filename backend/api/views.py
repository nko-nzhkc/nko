# Модуль представлений проекта.
from django.http import JsonResponse
from django.views import View
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .mixins import ViewListCreateMixinsSet
from .permissions import IsAdmin
from .serializers import (
    ContactSerializer,
    ForbiddenwordSerializer,
    CloudpaymentsSerializer,
    MixPlatSerializer,
)
from .utils import (
    add_contacts,
    handling_cloudpayment_data,
    mixplat_request_handler,
    send_request,
)
from contacts.models import Contact
from forbiddenwords.models import ForbiddenWord
from mixplat.models import MixPlat
from cloudpayments.models import CloudPayment


class ContactViewSet(viewsets.ModelViewSet):
    """Вьюсет контактов."""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

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


class MixplatViewSet(viewsets.ModelViewSet):
    """Вьюсет Mixplat."""

    queryset = MixPlat.objects.all()
    serializer_class = MixPlatSerializer

    @action(detail=False, url_path="payment_status", methods=("post",))
    def payment_status(self, request):
        """Метод получения данных от Mixplat."""
        return mixplat_request_handler(request)


class CloudPaymentsViewSet(viewsets.GenericViewSet):
    """
    Вьсюсет для Cloudpayment.
    """

    @action(detail=False, url_path="create_cloudpayment", methods=["post"])
    def create_cloudpayment(self, request):
        """
        Создание экзепмляра Cloudpayment.
        """
        serializer = CloudpaymentsSerializer(
            data=handling_cloudpayment_data(request)
        )
        if serializer.is_valid():
            serializer.save()
            return Response(dict(code=0), status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PaymentsListView(View):
    model = None

    def get(self, request, *args, **kwargs):
        mixplat_payments = MixPlat.objects.all()
        cloudpayment_payments = CloudPayment.objects.all()

        all_payments_list = mixplat_payments.union(cloudpayment_payments)
        all_payments_list = all_payments_list.order_by("-pub_date")

        payments_data = list(all_payments_list.values())

        return JsonResponse({"payments_list": payments_data})
