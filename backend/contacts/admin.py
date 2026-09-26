# Модуль админки модели контакты.
from django.contrib import admin
from donor_base.constants import EMPTY_VALUE

from contacts.models import Contact, Donor


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Админ зона контактов."""

    list_display = ("username", "email", "subject", "comment")
    empty_value_display = EMPTY_VALUE
    list_filter = ("username",)


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Админ зона доноров."""

    list_display = ("email", "subscription", "count_declined")
    empty_value_display = EMPTY_VALUE
    list_filter = ("email", "subscription", "count_declined")
