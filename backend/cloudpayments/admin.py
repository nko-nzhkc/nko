# Модуль админки модели пожертвований Cloudpayment.
from django.contrib import admin

from .models import CloudPayment
from donor_base.constants import EMPTY_VALUE


@admin.register(CloudPayment)
class CloudPaymentAdmin(admin.ModelAdmin):
    """Админ зона пожертвований Cloudpayment"""

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
