# Модуль разрешений API.
from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """Разрешение Администратора."""

    message = "Раздел только для Администратора."

    def has_permission(self, request, view):
        if request.user.is_authenticated:
            return request.user.is_admin or request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return request.user.is_admin or request.user.is_superuser
