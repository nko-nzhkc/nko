"""Тесты репозиториев API."""

from django.test import TestCase

from api.repositories import DonorRepository
from contacts.models import Donor


class DonorRepositoryTest(TestCase):
    """Проверяет выборку доноров."""

    def test_get_donors_returns_email_and_subscription(self):
        """Репозиторий возвращает данные, нужные Use Case."""
        Donor.objects.create(
            email="first@example.com",
            subscription="Active",
        )
        Donor.objects.create(
            email="second@example.com",
            subscription="Inactive",
        )

        donors = list(DonorRepository().get_donors())

        self.assertEqual(
            donors,
            [
                ("first@example.com", "Active"),
                ("second@example.com", "Inactive"),
            ],
        )
