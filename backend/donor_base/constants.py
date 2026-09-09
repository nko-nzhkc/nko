from enum import Enum


PAYMENT_METHOD_LENGTH = 64

ZERO = 0

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

BAD_COUNT = 3

BAD_STATUSES = ["Cancelled", "Declined", "failure"]
NEY_SUB_STAT = ["Lost", "Inactive"]


class Subscriptions(Enum):
    """Класс статусов подписок.

    Формат:
    name = (value, capitalized, group_id)

    velue:       русская расшифровка статуса
    capitalized: name в формате записи capitilized
    group_id:    ид группы.
    """

    ACTIVE = ("Подписка активна", "Active", "5")
    INACTIVE = ("Подписка отсутствует", "Inactive", "7")
    LOST = ("Подписка утрачена", "Lost", "9")

    def __new__(cls, value, capitalized, group_id):
        """
        Переопределение создания энум-констант.

        Нужно для быстрого обращения к атрибутам констант.
        """

        obj = object.__new__(cls)
        obj.value = value
        obj.value = capitalized
        obj.group_id = group_id
        return obj
