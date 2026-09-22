"""Celery-задачи API."""

import zapros
from donor_base import di
from donor_base.celery import app

from api.repositories import DonorRepository
from api.use_cases import SyncDonorsToUnisenderUseCase


@app.task(
    autoretry_for=(zapros.ZaprosError,),
    max_retries=2,
)
def send_users_to_unisender(donor_ids=None, overwrite_lists=1):
    """Отправляет доноров с повтором при ошибках zapros."""
    use_case = SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )
    use_case.execute(
        donor_ids=donor_ids,
        overwrite_lists=overwrite_lists,
    )


@app.task
def send_payment_email_task(email, list_id):
    """Отправляет письмо после завершения импорта контакта."""
    from api.utils import send_payment_email

    send_payment_email(email, list_id)
