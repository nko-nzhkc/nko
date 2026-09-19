import django
import os
import logging
from celery import Celery

logger = logging.getLogger("Celery_logger")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("celery.log")
handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "donor_base.settings")
django.setup()
app = Celery("donor_base")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.broker_connection_retry_on_startup = True
