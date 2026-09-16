"""Celery-задачи API."""

import zapros

from api.repositories import DonorRepository
from api.use_cases import SyncDonorsToUnisenderUseCase
from donor_base import di
from donor_base.celery import app


@app.task(
    autoretry_for=(zapros.ZaprosError,),
    max_retries=2,
)
def send_users_to_unisender():
    """Отправляет доноров с повтором при ошибках zapros."""
    use_case = SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )
    use_case.execute()
