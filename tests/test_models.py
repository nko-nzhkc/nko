"""Тесты поведения моделей."""

import pytest

from contacts.models import Contact, Donor
from donor_base.constants import SubscriptionStatuses
from forbiddenwords.models import ForbiddenWord


@pytest.mark.django_db
def test_model_string_representations(faker):
    """Строковые представления моделей возвращают пользовательские значения."""
    contact = Contact.objects.create_user(
        username="username",
        email=faker.unique.email(),
        subject="subject",
        comment="comment",
        password="password",
    )
    donor = Donor.objects.create(
        email="donor@example.com",
        subscription=SubscriptionStatuses.ACTIVE.capitalized,
    )
    forbidden_word = ForbiddenWord.objects.create(forbidden_word="spam")

    assert str(contact) == f"{contact.username} - {contact.email}"
    assert str(donor) == donor.email
    assert str(forbidden_word) == forbidden_word.forbidden_word
