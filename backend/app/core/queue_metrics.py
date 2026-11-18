from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import GaugeMetricFamily
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.models import Job
from app.db.session import SessionLocal


class QueueMetrics:
    def collect(self):
        persistent = GaugeMetricFamily(
            "analyst_job_records", "Persisted job counts", labels=["kind", "status", "failure_code"]
        )
        database = GaugeMetricFamily("analyst_job_metrics_database_up", "Job database is reachable")
        try:
            with SessionLocal() as db:
                counts = db.execute(
                    select(Job.kind, Job.status, Job.failure_code, func.count()).group_by(
                        Job.kind, Job.status, Job.failure_code
                    )
                )
                for kind, status, code, size in counts:
                    persistent.add_metric([kind, status, code or ""], size)
        except SQLAlchemyError:
            database.add_metric([], 0)
        else:
            database.add_metric([], 1)
            yield persistent
        yield database

        config = settings()
        if config.task_backend != "celery":
            return
        broker = GaugeMetricFamily("analyst_job_metrics_broker_up", "Redis job broker is reachable")
        backlog = GaugeMetricFamily(
            "analyst_broker_queue_depth", "Waiting deliveries on the default Celery queue"
        )
        try:
            with Redis.from_url(config.broker_url, socket_timeout=2, socket_connect_timeout=2) as redis:
                # Kombu's default Redis priority buckets for the default Celery queue.
                keys = ["celery", "celery\x06\x163", "celery\x06\x166", "celery\x06\x169"]
                with redis.pipeline(transaction=False) as commands:
                    for key in keys:
                        commands.llen(key)
                    depth = sum(commands.execute())
        except (RedisError, ValueError):
            broker.add_metric([], 0)
        else:
            broker.add_metric([], 1)
            backlog.add_metric([], depth)
            yield backlog
        yield broker


def queue_metrics() -> bytes:
    registry = CollectorRegistry()
    registry.register(QueueMetrics())
    return generate_latest(registry)
