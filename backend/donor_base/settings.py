import os
from pathlib import Path

from dotenv import load_dotenv

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

# Для работы на сервере
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL", "amqp://user:password@rabbitmq:5672//"
)

CELERY_ACCEPT_CONTENT = ["application/json"]

CELERY_TIMEZONE = "Europe/Moscow"

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_TIME_LIMIT = 30 * 60

CELERY_BEAT_SCHEDULE = {

}

# Константы проекта


CLOUDPAYMENTS_PUBLIC_ID = os.getenv("CLOUDPAYMENTS_PUBLIC_ID")
CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = os.getenv(
    "CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL"
)
CLOUDPAYMENTS_API_SECRET = os.getenv("CLOUDPAYMENTS_API_SECRET")
CLOUDPAYMENTS_API_TEST_URL = os.getenv("CLOUDPAYMENTS_API_TEST_URL")

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
