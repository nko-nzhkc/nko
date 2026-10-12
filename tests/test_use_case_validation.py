"""Тесты валидации параметров сценария синхронизации."""

import pytest
from faker import Faker

from api.repositories import DonorRepository
from api.use_cases import SyncDonorsToUnisenderUseCase
from donor_base import di


def test_execute_rejects_invalid_overwrite_lists(faker: Faker) -> None:
    """Сценарий отклоняет случайное значение вне протокола Unisender."""
    invalid_value = faker.pyint(min_value=2, max_value=100)
    use_case = SyncDonorsToUnisenderUseCase(
        repository=DonorRepository(),
        client=di.get_unisender_client(),
    )

    with pytest.raises(ValueError, match="overwrite_lists"):
        use_case.execute(overwrite_lists=invalid_value)
