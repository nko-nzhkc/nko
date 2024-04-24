# Модуль собственных валидаторов.
from django.core.exceptions import ValidationError

from forbiddenwords.models import ForbiddenWord


def forbidden_words_validator(value):
    """Валидация на запрещенные слова."""

    forbidden_words = ForbiddenWord.objects.values_list(
        "forbidden_word", flat=True
    )
    for word in forbidden_words:
        if word in value.lower():
            raise ValidationError("Содержит запрещенные слова.")
