from django.urls import include, path
from rest_framework import routers

from api.views import (
    CloudPaymentsViewSet,
    ContactViewSet,
    ForbiddenwordViewSet,
    MixplatViewSet,
    PaymentsListViewSet,
)

app_name = "api"

router_v1 = routers.SimpleRouter()
router_v1.register("contacts", ContactViewSet, basename="contacts")
router_v1.register(
    "forbiddenwords", ForbiddenwordViewSet, basename="forbiddenwords",
)
router_v1.register(
    "cloudpayments", CloudPaymentsViewSet, basename="cloudpayments",
)
router_v1.register("mixplat", MixplatViewSet, basename="mixplat")
router_v1.register("payments", PaymentsListViewSet, basename="payments")

urlpatterns = [
    path("", include(router_v1.urls)),
]
