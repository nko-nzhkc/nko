from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Donation
from .utils import send_email


@receiver(post_save, sender=Donation)
def send_donation_email(sender, instance, created, **kwargs):
    if created:
        subject = "The payment was successful"
        message = "Thank you for your donation!"
        send_email(instance.email, subject, message)
