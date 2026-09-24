# Модуль миксинов представления.
from rest_framework import mixins, viewsets


class ViewListCreateMixinsSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Сет миксинов: просмотр, создание."""
