import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'email_project.settings')

app = Celery('email_project')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks(['django_backend', 'fastapi_app'])

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')