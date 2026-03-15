"""Celery tasks for running scans in the background."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from ..celery_app import celery

from ..database import SessionLocal
from ..services.scan_service import ScanService


@celery.task(name="app.tasks.scan_tasks.run_scan")
def run_scan(scan_db_id: int) -> Dict[str, Any]:
    """Run a scan asynchronously in a Celery worker."""

    db = SessionLocal()
    try:
        service = ScanService(db)
        asyncio.run(service.start_scan(scan_db_id))
        return {
            "event": "scan_task_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "scan_db_id": scan_db_id,
        }
    except Exception as exc:
        return {
            "event": "scan_task_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "scan_db_id": scan_db_id,
            "error": str(exc),
        }
    finally:
        try:
            db.close()
        except Exception:
            pass
