"""Тесты собственных валидаторов."""

import pytest
from django.core.exceptions import ValidationError

from api.validators import forbidden_words_validator
from forbiddenwords.models import ForbiddenWord


@pytest.mark.django_db
def test_validator_accepts_clean_value() -> None:
    """Валидатор проходит по всем словам и не падает, если совпадений нет."""
    ForbiddenWord.objects.create(forbidden_word="spam")

    forbidden_words_validator("clean text")


@pytest.mark.django_db
def test_validator_rejects_forbidden_word() -> None:
    """Валидатор отклоняет значение, содержащее запрещённое слово."""
    ForbiddenWord.objects.create(forbidden_word="spam")

    with pytest.raises(ValidationError, match="Содержит запрещенные слова"):
        forbidden_words_validator("contains spam here")
