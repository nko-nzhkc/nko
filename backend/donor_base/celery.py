import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "donor_base.settings")
app = Celery("donor_base")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Представляет собой задачу,
    которая выгружает собственную информацию о запросе.
    """
    print(f"Request: {self.request!r}")
