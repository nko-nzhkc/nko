"""Celery-задачи API."""

import zapros
from donor_base import di
from donor_base.celery import app

from api.repositories import DonorRepository
from api.use_cases import SyncDonorsToUnisenderUseCase


@app.task(  # type: ignore[misc]
    autoretry_for=(zapros.ZaprosError,),
    max_retries=2,
)
def send_users_to_unisender(
    donor_ids: list[int] | None = None,
    overwrite_lists: int = 1,
) -> None:
    """Отправляет доноров с повтором при ошибках zapros."""
    use_case = SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )
    use_case.execute(
        donor_ids=donor_ids,
        overwrite_lists=overwrite_lists,
    )


@app.task  # type: ignore[misc]
def send_payment_email_task(
    email: str,
    list_id: int,
) -> None:
    """Отправляет письмо после завершения импорта контакта."""
    from api.unisender_service import send_payment_email

    send_payment_email(email, list_id)
