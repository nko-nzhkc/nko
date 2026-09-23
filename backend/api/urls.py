# Модуль API URLS проекта.
from django.urls import path

from .views import (
    StartContactSendView,
    GetContactsView,
    ForbiddenWordListView,
    MixplatView,
    CloudPaymentCreateView,
    PaymentsListView,
)

app_name = "api"

urlpatterns = [
    path(
        'contacts/start/',
        StartContactSendView.as_view(),
        name='start-contact-send',
    ),
    path(
        'contacts/get_contacts/',
        GetContactsView.as_view(),
        name='get-contacts',
    ),
    path(
        'forbiddenwords/',
        ForbiddenWordListView.as_view(),
        name='forbiddenwords',
    ),
    path(
        'mixplat/',
        MixplatView.as_view(),
        name='mixplat',
    ),
    path(
        'cloudpayments/',
        CloudPaymentCreateView.as_view(),
        name='cloudpayments',
    ),
    path(
        'payments/',
        PaymentsListView.as_view(),
        name='payments-list',
    ),
]
