from enum import Enum
from typing import ClassVar


class PaymentStatuses(Enum):
    """Класс статусов платежей."""

    CANCELLED = "Cancelled"
    DECLINED = "Declined"
    FAILURE = "failure"


class SubscriptionStatuses(Enum):
    # TODO: поправить докстринг с учетом изменения логики переопределения
    # value и verbosed значения
    """Класс статусов подписок.

    Формат:
    name = (verbosed, capitalized, group_id)

    value:       русская расшифровка статуса
    capitalized: name в формате записи capitilized
    group_id:    ид группы.
    """

    ACTIVE = ("Подписка активна", "Active", "5")
    INACTIVE = ("Подписка отсутствует", "Inactive", "7")
    LOST = ("Подписка утрачена", "Lost", "9")

    verbosed: ClassVar[str]
    capitalized: ClassVar[str]
    group_id: ClassVar[str]

    def __new__(cls, verbosed, capitalized, group_id):
        """
        Переопределение создания энум-констант.

        Нужно для быстрого обращения к атрибутам констант.
        """

        obj = object.__new__(cls)
        obj._value_ = (verbosed, capitalized, group_id)
        obj.verbosed = verbosed
        obj.capitalized = capitalized
        obj.group_id = group_id
        return obj


NEGATIVE_SUB_STAT = (
    SubscriptionStatuses.LOST.capitalized,
    SubscriptionStatuses.INACTIVE.capitalized
    )

PAYMENT_METHOD_LENGTH = 64

DEFAULT_DONATION = 0

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

EMPTY_VALUE = "-пусто-"

MAX_USERNAME_LENGTH = 150
MAX_EMAIL_LENGTH = 255
MAX_SUBJECT_LENGTH = 255
MAX_FORBIDDEN_WORLD_LENGTH = 100
MAX_CURRENCY_LENGTH = 10
MAX_PAYMENT_OPERATOR_LENGTH = 250

MAX_PAYMENT_ID_LENGTH = 100
MAX_PAYMENT_STATUS_LENGTH = 100

BAD_PAYMENTS_COUNT = 3
