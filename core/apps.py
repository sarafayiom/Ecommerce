from django.apps import AppConfig
from django.core.signals import request_started


def start_scheduler(sender, **kwargs):
    
    request_started.disconnect(start_scheduler)

    from apscheduler.schedulers.background import BackgroundScheduler
    from .tasks import process_daily_sales_chunks

    scheduler = BackgroundScheduler()

    scheduler.add_job(process_daily_sales_chunks, "interval", minutes=1)

    scheduler.start()
    print(" APScheduler started successfully within 'core' app!")


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"  
    def ready(self):
        request_started.connect(start_scheduler)
