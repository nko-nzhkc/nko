from donor_base.settings import *  # noqa

DATABASES: dict[str, dict[str, str]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
MOCK_BASE_URL = "http://test.local"

CLOUDPAYMENTS_PUBLIC_ID: str = "test_public_id"
CLOUDPAYMENTS_API_SECRET: str = "test_api_secret"
CLOUDPAYMENTS_SUBSCRIPTION_FIND_URL: str = (
    f"{MOCK_BASE_URL}/v1/cloudpayments/subscriptions/find"
)

UNISENDER_API_KEY: str = "test_unisender_key"
TEMPLATE_ID: str = "test_template_id"
DEFAULT_FROM_EMAIL: str = "test_from@example.com"
UNISENDER_SENDER_NAME: str = "Test Sender"
URL_GET_TEMP: str = f"{MOCK_BASE_URL}/v1/unisender/templates"
URL_SEND_EMAIL: str = f"{MOCK_BASE_URL}/v1/unisender/messages/send"
IMPORT_UNISENDER: str = f"{MOCK_BASE_URL}/v1/unisender/contacts/import"
