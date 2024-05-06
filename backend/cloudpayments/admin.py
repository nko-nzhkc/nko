# Модуль админки модели пожертвований Cloudpayment.
from django.conf import settings
from django.contrib import admin

from .models import CloudPayment


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
        "payment_status",
        "currency",
    )
    empty_value_display = settings.EMPTY_VALUE
    list_filter = ("pub_date", "payment_status", "currency")
