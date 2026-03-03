"""Activity logs API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import LogResponse, LogListResponse
from ..models import User, Log, LogLevel
from ..utils.auth import get_current_user

router = APIRouter()


@router.get("/logs", response_model=LogListResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    level: Optional[str] = None,
    component: Optional[str] = None,
    scan_id: Optional[int] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get activity logs"""
    query = db.query(Log)
    
    # Filter by level if provided
    if level and level != "all":
        try:
            level_enum = LogLevel[level.upper()]
            query = query.filter(Log.level == level_enum)
        except KeyError:
            pass
    
    # Filter by component if provided
    if component and component != "all":
        query = query.filter(Log.component == component)
    
    # Filter by scan_id if provided
    if scan_id:
        query = query.filter(Log.scan_id == scan_id)
    
    # Search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Log.message.ilike(search_pattern)) |
            (Log.component.ilike(search_pattern)) |
            (Log.details.ilike(search_pattern))
        )
    
    # Count total
    total = query.count()
    
    # Paginate and order by timestamp
    logs = query.order_by(Log.timestamp.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/logs/components")
async def list_components(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of unique log components"""
    components = db.query(Log.component).distinct().all()
    return {"components": [c[0] for c in components]}


@router.delete("/logs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_logs(
    older_than_days: int = Query(None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear old logs"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    query = db.query(Log)
    
    if older_than_days:
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        query = query.filter(Log.timestamp < cutoff_date)
    
    query.delete()
    db.commit()
    
    return None


@router.get("/logs/{log_id}", response_model=LogResponse)
async def get_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific log entry"""
    log = db.query(Log).filter(Log.id == log_id).first()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log entry not found"
        )
    
    return log
