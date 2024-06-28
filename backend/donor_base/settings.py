import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = os.getenv("DEBUG", "").lower() in ["true", "yes", "1"]

# ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")
ALLOWED_HOSTS = ['127.0.0.1']

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api.apps.ApiConfig",
    "contacts.apps.ContactsConfig",
    "forbiddenwords.apps.ForbiddenwordsConfig",
    "cloudpayments.apps.CloudpaymentsConfig",
    "mixplat.apps.MixplatConfig",
    "acquiring.apps.AcquiringConfig",
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# # postgresql
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("POSTGRES_DB", "django"),
#         "USER": os.getenv("POSTGRES_USER", "django"),
#         "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
#         "HOST": os.getenv("DB_HOST", ""),
#         "PORT": os.getenv("DB_PORT", 5432),
#     }
# }

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

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", "amqp://myuser:mypassword@localhost:5672/myvhost"
)

CELERY_ACCEPT_CONTENT = ["application/json"]

CELERY_TIMEZONE = "Europe/Moscow"

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_TIME_LIMIT = 30 * 60

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

# Константы проекта

PAYMENT_METHOD_LENGTH = 64

ZERO = 0
THREE_HUNDRED = 300
FIVE_HUNDRED = 500
THOUSAND = 1000
THREE_THOUSAND = 3000
AMOUNT = [
    (ZERO, "0"),
    (THREE_HUNDRED, "300"),
    (FIVE_HUNDRED, "500"),
    (THOUSAND, "1000"),
    (THREE_THOUSAND, "3000"),
]


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
CLOUDPAYMENTS_API_SECRET = os.getenv("CLOUDPAYMENTS_API_SECRET")
CLOUDPAYMENTS_API_TEST_URL = "https://api.cloudpayments.ru/test"

MAX_PAYMENT_ID_LENGTH = 100
MAX_PAYMENT_STATUS_LENGTH = 100
MAX_USER_COMMENT_LENGTH = 100
DEFAULT_CONF = {
    "base_url": "https://api.unisender.com",
    "lang": "en",
    "format": "json",
    "api_key": None,
    "platform": None,
}
