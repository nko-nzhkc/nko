# Модуль админки запрещенных слов.
from django.conf import settings
from django.contrib import admin

from .models import ForbiddenWord


@admin.register(ForbiddenWord)
class ForbiddenWordAdmin(admin.ModelAdmin):
    """Админ зона для запрещенных слов."""

    list_display = ("forbidden_word",)
    empty_value_display = settings.EMPTY_VALUE
    list_filter = ("forbidden_word",)
