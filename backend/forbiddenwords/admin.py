# Модуль админки запрещенных слов.
from django.contrib import admin

from .models import ForbiddenWord
from donor_base.constants import EMPTY_VALUE


@admin.register(ForbiddenWord)
class ForbiddenWordAdmin(admin.ModelAdmin):
    """Админ зона для запрещенных слов."""

    list_display = ("forbidden_word",)
    empty_value_display = EMPTY_VALUE
    list_filter = ("forbidden_word",)
