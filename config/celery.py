import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('crypto_platform')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    'update-prices-every-hour': {
        'task': 'apps.tasks.price_tasks.update_all_token_prices',
        'schedule': crontab(minute=0),  # Every hour
    },
    'credit-yield-every-hour': {
        'task': 'apps.tasks.yield_task.credit_hourly_yield',
        'schedule': crontab(minute=5),  # 5 min past each hour
    },
    'send-daily-emails': {
        'task': 'apps.tasks.email_tasks.send_daily_email_to_all_users',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')