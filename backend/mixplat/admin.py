# Модуль админки модели платежа Mixplat.
from django.contrib import admin

from .models import MixPlat
from donor_base.constants import EMPTY_VALUE


@admin.register(MixPlat)
class DonationAdmin(admin.ModelAdmin):
    """Админ зона платежа Mixplat."""

    list_display = (
        "email",
        "donat",
        "custom_donat",
        "payment_method",
        "monthly_donat",
        "subscription",
        "pub_date",
        "payment_id",
        "status",
        "user_account_id",
        "date_created",
        "date_processed",
        "payment_operator",
    )
    empty_value_display = EMPTY_VALUE
    list_filter = ("pub_date", "status")
