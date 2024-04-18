from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Donation


@receiver(post_save, sender=Donation)
def send_donation_email(sender, instance, created, **kwargs):
    if created:
        send_mail(
            "Thank you for your donation!",
            "Thank you for your donation!",
            "from@example.com",
            [instance.email],
            fail_silently=False,
        )
