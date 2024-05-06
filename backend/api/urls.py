# Модуль API URLS проекта.
from django.urls import include, path
from rest_framework import routers

from .views import (
    ContactViewSet,
    DonationViewSet,
    ForbiddenwordViewSet,
    CloudPaymentsViewSet,
    MixplatViewSet,
)

app_name = "api"

router_v1 = routers.DefaultRouter()
router_v1.register("donations", DonationViewSet, basename="donations")
router_v1.register("contacts", ContactViewSet, basename="contacts")
router_v1.register(
    "forbiddenwords", ForbiddenwordViewSet, basename="forbiddenwords"
)
router_v1.register(
    "cloudpayments", CloudPaymentsViewSet, basename="cloudpayments"
)
router_v1.register("mixplat", MixplatViewSet, basename="mixplat")

urlpatterns = [
    path("", include(router_v1.urls)),
]
