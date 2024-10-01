import os
from pathlib import Path

from dotenv import load_dotenv

# from celery.schedules import crontab
# from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG", "").lower() in ["true", "yes", "1"]

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "api.apps.ApiConfig",
    "contacts.apps.ContactsConfig",
    "forbiddenwords.apps.ForbiddenwordsConfig",
    "cloudpayments.apps.CloudpaymentsConfig",
    "mixplat.apps.MixplatConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

AUTH_USER_MODEL = "contacts.Contact"

ROOT_URLCONF = "donor_base.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "donor_base.wsgi.application"

# sqlite3
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

# postgresql
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "django"),
        "USER": os.getenv("POSTGRES_USER", "django"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", 5432),
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "django_info.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["file"],
        "level": "INFO",
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",  # noqa: E501
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",  # noqa: E501
    },
]

LANGUAGE_CODE = "ru-RU"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",  # noqa: E501
    "PAGE_SIZE": 3,
}

STATIC_URL = os.getenv("STATIC_URL", "/static/")

# Папка со статикой внутри контейнера backend
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Для локального запуска запустить контейнер Docker командой
# sudo docker run -d --name rabbitmq
# -p 5672:5672 -p 15672:15672
# -e RABBITMQ_DEFAULT_USER=user
# -e RABBITMQ_DEFAULT_PASS=password
# rabbitmq:3-management
# CELERY_BROKER_URL = os.getenv(
#     "CELERY_BROKER_URL", "amqp://user:password@localhost:5672//"
# )

# Для работы на сервере
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", "amqp://user:password@rabbitmq:5672//"
)

CELERY_ACCEPT_CONTENT = ["application/json"]

CELERY_TIMEZONE = "Europe/Moscow"

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_TIME_LIMIT = 30 * 60

CELERY_BEAT_SCHEDULE = {
    # Планируем отправку доноров, например ежедневно в 3 ночи.
    # 'run-every-day-at-midnight': {
    #     'task': 'api.tasks.send_users_to_unisender',
    #     'schedule': crontab(hour=3, minute=0),
    # },
    # Периодическая такса для проверки,
    # будет писать в файл celery.log раз в 10 секунд
    # "run-every-10-seconds": {
    #     "task": "api.tasks.send_users_to_unisender",
    #     "schedule": timedelta(seconds=10),
    # },
}

# Константы проекта

PAYMENT_METHOD_LENGTH = 64

ZERO = 0
THREE_HUNDRED = 300
FIVE_HUNDRED = 500
THOUSAND = 1000
THREE_THOUSAND = 3000

# AMOUNT = [
#     (ZERO, "0"),
#     (THREE_HUNDRED, "300"),
#     (FIVE_HUNDRED, "500"),
#     (THOUSAND, "1000"),
#     (THREE_THOUSAND, "3000"),
# ]

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

EMPTY_VALUE = "-пусто-"

MAX_USERNAME_LENGTH = 150
MAX_EMAIL_LENGTH = 255
MAX_SUBJECT_LENGTH = 255
MAX_FORBIDDEN_WORLD_LENGTH = 100
MAX_CURRENCY_LENGTH = 10
MAX_PAYMENT_OPERATOR_LENGTH = 250

# TODO Необходимо разместить PUBLIC_ID, API_SECRET в SECRETS
CLOUDPAYMENTS_PUBLIC_ID = os.getenv("CLOUDPAYMENTS_PUBLIC_ID")
CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = os.getenv(
    "CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL"
)
CLOUDPAYMENTS_API_SECRET = os.getenv("CLOUDPAYMENTS_API_SECRET")
CLOUDPAYMENTS_API_TEST_URL = os.getenv("CLOUDPAYMENTS_API_TEST_URL")

MAX_PAYMENT_ID_LENGTH = 100
MAX_PAYMENT_STATUS_LENGTH = 100
MAX_USER_COMMENT_LENGTH = 100
DEFAULT_CONF = {
    "base_url": "https://api.unisender.com",
    "lang": "en",
    "format": "json",
    "api_key": os.getenv("UNISENDER_API_KEY"),
    "platform": None,
}

EXPORT_UNISENDER = "https://api.unisender.com/ru/api/async/exportContacts"
IMPORT_UNISENDER = "https://api.unisender.com/ru/api/importContacts"
UNISENDER_API_KEY = os.getenv("UNISENDER_API_KEY")
NOTIFY_URL = "https://foodgrampyengineer.ru/api/contacts/get_contacts/"
URL_SEND_EMAIL = "https://api.unisender.com/ru/api/sendEmail"
URL_GET_TEMP = "https://api.unisender.com/ru/api/getTemplate"
TEMPLATE_ID = os.getenv("TEMPLATE_ID")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
UNISENDER_SENDER_NAME = os.getenv("UNISENDER_SENDER_NAME")

SUBSCRIPTION_CHOICES = [
    ("Active", "Подписка активна"),
    ("Inactive", "Подписка отсутствует"),
    ("Lost", "Подписка утрачена"),
]
GROUPS = {
    "5": "Active",
    "Active": "5",
    "7": "Inactive",
    "Inactive": "7",
    "9": "Lost",
    "Lost": "9",
}
BAD_COUNT = 3
BAD_STATUSES = ["Cancelled", "Declined", "failure"]
NEY_SUB_STAT = ["Lost", "Inactive"]
