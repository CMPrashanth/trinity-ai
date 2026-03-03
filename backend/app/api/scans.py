"""Scan management API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..schemas import ScanCreate, ScanResponse, ScanListResponse, ScanStatusEnum
from ..models import User, Scan, ScanStatus, ScanProfile
from ..utils.auth import get_current_user
from ..services.scan_service import ScanService

router = APIRouter()


@router.post("/scans", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan_data: ScanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create and initiate a new scan"""
    scan_service = ScanService(db)
    scan = await scan_service.create_scan(scan_data, current_user.id)
    
    # Trigger background scan task (this would normally start the actual scan)
    # For now, we'll just mark it as running
    await scan_service.start_scan(scan.id)
    
    return scan


@router.get("/scans", response_model=ScanListResponse)
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of scans for current user"""
    query = db.query(Scan).filter(Scan.user_id == current_user.id)
    
    # Filter by status if provided
    if status:
        try:
            status_enum = ScanStatus[status.upper()]
            query = query.filter(Scan.status == status_enum)
        except KeyError:
            pass
    
    # Count total
    total = query.count()
    
    # Paginate
    scans = query.order_by(Scan.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "scans": scans,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific scan details"""
    scan = db.query(Scan).filter(
        Scan.scan_id == scan_id,
        Scan.user_id == current_user.id
    ).first()
    
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    return scan


@router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a scan"""
    scan = db.query(Scan).filter(
        Scan.scan_id == scan_id,
        Scan.user_id == current_user.id
    ).first()
    
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    db.delete(scan)
    db.commit()
    
    return None


@router.post("/scans/{scan_id}/cancel")
async def cancel_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a running scan"""
    scan = db.query(Scan).filter(
        Scan.scan_id == scan_id,
        Scan.user_id == current_user.id
    ).first()
    
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    if scan.status != ScanStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scan is not running"
        )
    
    scan.status = ScanStatus.CANCELLED
    scan.end_time = datetime.utcnow()
    db.commit()
    
    return {"message": "Scan cancelled successfully"}
