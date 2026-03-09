"""Celery tasks for CVE feed synchronization and automation hooks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from celery import shared_task

from ..config import settings
from ..services.cve_feed_service import CVEFeedService


def _notify_n8n(payload: Dict[str, Any]) -> None:
    if not settings.N8N_WEBHOOK_URL:
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(settings.N8N_WEBHOOK_URL, json=payload)
    except Exception as exc:  # pragma: no cover - best effort notification
        print(f"⚠️ n8n webhook notification failed: {exc}")


@shared_task(name="app.tasks.cve_tasks.sync_cve_feed")
def sync_cve_feed() -> Dict[str, Any]:
    """Periodic CVE sync task executed by Celery worker."""
    service = CVEFeedService()

    try:
        result = asyncio.run(service.sync_latest())
        payload = {
            "event": "cve_sync_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "new_cves": result.get("new_cves", 0),
            "severity_breakdown": result.get("severity_breakdown", {}),
            "since": result.get("since"),
            "until": result.get("until"),
        }
        _notify_n8n(payload)
        return payload
    except Exception as exc:
        payload = {
            "event": "cve_sync_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error": str(exc),
        }
        _notify_n8n(payload)
        raise
