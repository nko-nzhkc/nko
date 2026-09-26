from enum import Enum
from typing import Self


class FailedPaymentStatuses(Enum):
    """Класс статусов не прошедших платежей."""

    CANCELLED = "Cancelled"
    DECLINED = "Declined"
    FAILURE = "failure"


class SubscriptionStatuses(Enum):
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

    verbosed: str
    capitalized: str
    group_id: str

    def __new__(
        cls,
        verbosed: str,
        capitalized: str,
        group_id: str,
    ) -> Self:
        """
        Переопределение создания энум-констант.

        Нужно для быстрого обращения к атрибутам констант.
        """
        status = object.__new__(cls)
        status._value_ = (verbosed, capitalized, group_id)
        status.verbosed = verbosed
        status.capitalized = capitalized
        status.group_id = group_id
        return status


NEGATIVE_SUB_STAT = (
    SubscriptionStatuses.LOST.capitalized,
    SubscriptionStatuses.INACTIVE.capitalized,
)

PAYMENT_METHOD_LENGTH = 64

DEFAULT_DONATION = 0

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_TZ = "UTC"

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
