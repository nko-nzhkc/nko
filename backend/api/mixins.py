# Модуль миксинов представления.
from typing import TypeVar

from django.db.models import Model
from rest_framework import mixins, viewsets

ModelT = TypeVar("ModelT", bound=Model)


class ViewListCreateMixinsSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet[ModelT],
):
    """Сет миксинов: просмотр, создание."""
