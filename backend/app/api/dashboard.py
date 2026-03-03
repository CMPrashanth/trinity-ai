"""Dashboard-specific API routes used by the frontend overview widgets."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..utils.auth import get_current_user
from ..models import User, Log, LogLevel, Scan
from ..schemas import DashboardActivityItem, DashboardActivityResponse

router = APIRouter(prefix="/dashboard")


def _map_log_to_activity(log: Log) -> DashboardActivityItem:
    """Convert a Log ORM object into a dashboard activity item."""
    extra = log.extra_data or {}
    message = log.message or ""
    details = log.details or None

    # Prefer explicit event type from log metadata when present
    event_type = (extra.get("event_type") or extra.get("type") or "").lower()

    if event_type not in {
        "scan_start",
        "vuln_found",
        "scan_complete",
        "error",
        "retry",
        "circuit_break",
    }:
        lowered_message = message.lower()
        if "circuit" in lowered_message or "breaker" in lowered_message:
            event_type = "circuit_break"
        elif "retry" in lowered_message or "self-heal" in lowered_message:
            event_type = "retry"
        elif "vuln" in lowered_message or "cve" in lowered_message:
            event_type = "vuln_found"
        elif log.level == LogLevel.SUCCESS:
            event_type = "scan_complete"
        elif log.level == LogLevel.ERROR:
            event_type = "error"
        else:
            event_type = "scan_start"

    target = None
    if isinstance(extra, dict):
        target = extra.get("target") or extra.get("host") or extra.get("asset")

    return DashboardActivityItem(
        id=log.id,
        type=event_type,
        message=message,
        target=target,
        timestamp=log.timestamp or datetime.utcnow(),
        details=details,
    )


@router.get("/activity", response_model=DashboardActivityResponse)
async def get_dashboard_activity(
    limit: int = Query(5, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent activity items for the dashboard feed."""
    logs = (
        db.query(Log)
        .join(Scan, Log.scan_id == Scan.id)
        .filter(Scan.user_id == current_user.id)
        .order_by(Log.timestamp.desc())
        .limit(limit)
        .all()
    )

    activities = [_map_log_to_activity(log) for log in logs]

    return DashboardActivityResponse(activities=activities)
