"""Vulnerability management API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import (
    VulnerabilityResponse,
    VulnerabilityListResponse,
    VulnerabilityStats,
    VulnerabilitySeverityBreakdown,
)
from ..models import User, Vulnerability, SeverityLevel, VulnerabilityStatus
from ..utils.auth import get_current_user

router = APIRouter()


@router.get("/vulnerabilities", response_model=VulnerabilityListResponse)
async def list_vulnerabilities(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of vulnerabilities"""
    query = db.query(Vulnerability)
    
    # Filter by severity if provided
    if severity and severity != "all":
        try:
            severity_enum = SeverityLevel[severity.upper()]
            query = query.filter(Vulnerability.severity == severity_enum)
        except KeyError:
            pass
    
    # Filter by status if provided
    if status and status != "all":
        try:
            status_enum = VulnerabilityStatus[status.upper()]
            query = query.filter(Vulnerability.status == status_enum)
        except KeyError:
            pass
    
    # Search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Vulnerability.cve.ilike(search_pattern)) |
            (Vulnerability.title.ilike(search_pattern)) |
            (Vulnerability.target.ilike(search_pattern))
        )
    
    # Count total
    total = query.count()
    
    # Paginate and order by severity
    severity_order = {
        SeverityLevel.CRITICAL: 0,
        SeverityLevel.HIGH: 1,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.LOW: 3,
        SeverityLevel.INFO: 4
    }
    
    vulnerabilities = query.order_by(Vulnerability.discovered_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "vulnerabilities": vulnerabilities,
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/vulnerabilities/stats", response_model=VulnerabilityStats)
async def get_vulnerability_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get vulnerability statistics"""
    severity_counts = VulnerabilitySeverityBreakdown(
        critical=db.query(Vulnerability).filter(Vulnerability.severity == SeverityLevel.CRITICAL).count(),
        high=db.query(Vulnerability).filter(Vulnerability.severity == SeverityLevel.HIGH).count(),
        medium=db.query(Vulnerability).filter(Vulnerability.severity == SeverityLevel.MEDIUM).count(),
        low=db.query(Vulnerability).filter(Vulnerability.severity == SeverityLevel.LOW).count(),
        info=db.query(Vulnerability).filter(Vulnerability.severity == SeverityLevel.INFO).count(),
    )

    total = (
        severity_counts.critical
        + severity_counts.high
        + severity_counts.medium
        + severity_counts.low
        + severity_counts.info
    )

    return VulnerabilityStats(total=total, by_severity=severity_counts)


@router.get("/vulnerabilities/{vuln_id}", response_model=VulnerabilityResponse)
async def get_vulnerability(
    vuln_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific vulnerability details"""
    vulnerability = db.query(Vulnerability).filter(Vulnerability.vuln_id == vuln_id).first()
    
    if not vulnerability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vulnerability not found"
        )
    
    return vulnerability


@router.patch("/vulnerabilities/{vuln_id}/status")
async def update_vulnerability_status(
    vuln_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update vulnerability status"""
    vulnerability = db.query(Vulnerability).filter(Vulnerability.vuln_id == vuln_id).first()
    
    if not vulnerability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vulnerability not found"
        )
    
    try:
        status_enum = VulnerabilityStatus[new_status.upper()]
        vulnerability.status = status_enum
        db.commit()
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value"
        )
    
    return {"message": "Status updated successfully"}


@router.delete("/vulnerabilities/{vuln_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vulnerability(
    vuln_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a vulnerability"""
    vulnerability = db.query(Vulnerability).filter(Vulnerability.vuln_id == vuln_id).first()
    
    if not vulnerability:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vulnerability not found"
        )
    
    db.delete(vulnerability)
    db.commit()
    
    return None
