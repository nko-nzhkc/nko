# Модуль собственных валидаторов.
from django.core.exceptions import ValidationError
from forbiddenwords.models import ForbiddenWord


def forbidden_words_validator(word_input):
    """Валидация на запрещенные слова."""
    forbidden_words = ForbiddenWord.objects.values_list(
        "forbidden_word",
        flat=True,
    )
    for word in forbidden_words:
        if word in word_input.lower():
            raise ValidationError("Содержит запрещенные слова.")
