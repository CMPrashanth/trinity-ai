"""Celery application configuration for background CVE synchronization tasks."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from .config import settings


celery = Celery(
    "trinity",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

sync_hours = max(1, int(settings.CVE_SYNC_INTERVAL_HOURS))
celery.conf.beat_schedule = {
    "cve-sync-schedule": {
        "task": "app.tasks.cve_tasks.sync_cve_feed",
        "schedule": crontab(minute=0, hour=f"*/{sync_hours}"),
    }
}
celery.conf.timezone = "UTC"
celery.conf.task_serializer = "json"
celery.conf.accept_content = ["json"]
celery.conf.result_serializer = "json"

# Ensure task auto-discovery when worker starts.
celery.autodiscover_tasks(["app.tasks"])
