from django.dispatch import receiver
from django.db.models.signals import post_save

from . import send_failed_payment_email
from .models import Donation


@receiver(post_save, sender=Donation)
def payment_rejected_handler(sender, instance, created, **kwargs):
    if not created and instance.status == "rejected":
        user_email = instance.user.email
        message = f"Ваш платеж на {instance.amount} был отклонен."
        send_failed_payment_email(user_email, message)
