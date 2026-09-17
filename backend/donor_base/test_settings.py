from donor_base.settings import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL = 'http://mock.net/subscription/find'
CLOUDPAYMENTS_PUBLIC_ID = 'test_id'
CLOUDPAYMENTS_API_SECRET = 'test_secret'

IMPORT_UNISENDER = 'http://mock.net/unisender/import'
UNISENDER_API_KEY = 'test_key'
