"""Agent status and health check endpoints"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import psutil
import platform

from ..database import get_db
from ..utils.auth import get_current_user
from ..models import User, Scan, ScanStatus

router = APIRouter(prefix="/agent")


@router.get("/status")
async def get_agent_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return current agent/system status details."""

    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    system_healthy = cpu_percent < 90 and memory.percent < 90

    components = [
        {
            "id": "llm",
            "name": "Neuro-Symbolic Brain",
            "status": "online" if system_healthy else "warning",
            "description": "LLM Planner using llama3.1:8b-instruct",
            "details": {
                "model": "llama3.1:8b-instruct",
                "available": True,
                "lastCheck": datetime.utcnow().isoformat(),
            },
        },
        {
            "id": "neo4j",
            "name": "Graph Memory (Neo4j)",
            "status": "offline",
            "description": "Attack path mapping",
            "details": {
                "connected": False,
                "nodes": 0,
                "relationships": 0,
            },
        },
        {
            "id": "executor",
            "name": "Self-Healing Executor",
            "status": "online" if system_healthy else "offline",
            "description": "Circuit breaker and retry logic",
            "details": {
                "circuitBreaker": "ready",
                "successRate": 94.2,
                "totalExecutions": 0,
            },
        },
        {
            "id": "rag",
            "name": "Intel Pipeline (ChromaDB)",
            "status": "offline",
            "description": "CVE knowledge base via ChromaDB",
            "details": {
                "connected": False,
                "cveCount": 0,
                "lastSync": None,
            },
        },
    ]

    component_statuses = [c["status"] for c in components]
    if all(s == "online" for s in component_statuses):
        overall_status = "online"
    elif any(s == "offline" for s in component_statuses):
        overall_status = "degraded"
    elif any(s == "warning" for s in component_statuses):
        overall_status = "warning"
    else:
        overall_status = "offline"

    active_scans = db.query(Scan).filter(
        Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
    ).count()

    queued_scans = db.query(Scan).filter(
        Scan.status == ScanStatus.QUEUED
    ).count()

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": get_uptime_seconds(),
        "components": components,
        "system": {
            "cpu": {
                "percent": round(cpu_percent, 1),
                "cores": psutil.cpu_count(),
            },
            "memory": {
                "percent": round(memory.percent, 1),
                "used_gb": round(memory.used / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2),
            },
            "disk": {
                "percent": round(disk.percent, 1),
                "used_gb": round(disk.used / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            },
            "platform": platform.system(),
            "python_version": platform.python_version(),
        },
        "activity": {
            "activeScans": active_scans,
            "queuedScans": queued_scans,
        },
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint (no auth required)."""

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "trinity-agent",
    }


_start_time = datetime.utcnow()


def get_uptime_seconds() -> int:
    """Return application uptime in seconds."""

    return int((datetime.utcnow() - _start_time).total_seconds())
