from celery import Celery

from app.core.config import settings

config = settings()
celery = Celery("analyst", broker=config.redis_url or "memory://")
celery.conf.update(
    task_ignore_result=True,
    task_always_eager=config.eager,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=config.job_timeout,
    task_soft_time_limit=config.job_timeout - 2,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 360},
    beat_schedule={"poll-analysis": {"task": "analyst.dispatch_due", "schedule": 30}},
)
