"""CVE / ChromaDB utility endpoints (seed + search) for demos and integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from ..utils.auth import get_current_user
from ..models import User
from ..services.vector_service import VectorService
from ..services.cve_feed_service import CVEFeedService


router = APIRouter(prefix="/cves")


class SeedRequest(BaseModel):
    reset: bool = False


class LabSeedRequest(BaseModel):
    reset: bool = False
    apps: Optional[list[str]] = None
    per_keyword: int = 15
    max_total: int = 120


@router.get("/status")
async def chroma_status(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns simple ChromaDB status for the current backend instance."""

    service = VectorService()
    if not service.collection:
        return {
            "status": "unavailable",
            "message": "ChromaDB collection not available (fallback mode)",
        }

    count = service.collection.count()

    state_paths = [Path("/app/cve_sync_state.json"), Path("cve_sync_state.json")]
    last_sync: Optional[Dict[str, Any]] = None
    for p in state_paths:
        if not p.exists():
            continue
        try:
            import json

            last_sync = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            last_sync = None
        break

    return {
        "status": "ok",
        "collection": "cve_knowledge_base",
        "count": count,
        "lastSyncState": last_sync,
        "viewer": {"id": current_user.id, "email": current_user.email},
    }


@router.post("/seed-demo")
async def seed_demo_cves(
    req: SeedRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Seeds ChromaDB with a curated set of famous CVEs (safe metadata only)."""

    service = VectorService()
    if not service.collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChromaDB collection not available; cannot seed demo CVEs",
        )

    try:
        added = await service.seed_demo_cves(reset=req.reset)
        return {
            "message": "Seeded demo CVEs",
            "added": added,
            "count": service.collection.count(),
            "seededBy": current_user.email,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo CVEs: {exc}",
        )


@router.post("/seed-lab")
async def seed_lab_cves(
    req: LabSeedRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Seeds ChromaDB with real CVEs from NVD tagged for the vulnerable lab apps.

    This intentionally uses NVD keywordSearch (no fabricated CVE IDs).
    """

    service = VectorService()
    if not service.collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ChromaDB collection not available; cannot seed lab CVEs",
        )

    if req.reset:
        await service.clear_collection()

    app_keywords: Dict[str, list[str]] = {
        # Broad but useful: WebGoat is a Spring app; these keywords usually produce
        # relevant CVEs that exercise the enrichment flow.
        "webgoat": ["spring framework", "spring boot", "apache tomcat", "log4j"],
        # Juice Shop is Node/JS ecosystem; these keywords seed CVEs commonly surfaced
        # in web stacks and help validate toolchain behavior.
        "juiceshop": ["node.js", "express", "angular"],
    }

    requested = [a.lower().strip() for a in (req.apps or ["webgoat", "juiceshop"]) if str(a).strip()]
    unknown = [a for a in requested if a not in app_keywords]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown apps: {unknown}. Supported: {sorted(app_keywords.keys())}",
        )

    feed = CVEFeedService(vector_service=service)
    all_records: list[Dict[str, Any]] = []
    for app in requested:
        records = await feed.search_by_keywords(
            app_keywords[app],
            per_keyword=req.per_keyword,
            max_total=req.max_total,
            extra_metadata={"source": "nvd", "seeded_by": current_user.email, "app": app},
        )
        all_records.extend(records)

    # Dedupe across apps/keywords.
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in all_records:
        cve_id = item.get("cve_id")
        if cve_id:
            by_id[cve_id] = item

    records = list(by_id.values())
    if records:
        await service.bulk_add_cves(records)

    return {
        "message": "Seeded lab CVEs",
        "apps": requested,
        "added": len(records),
        "count": service.collection.count(),
        "seededBy": current_user.email,
    }


@router.get("/search")
async def search_cves(
    q: str = Query(..., min_length=2, description="Free-text query (e.g., 'openssl tls', 'apache httpd')"),
    n: int = Query(5, ge=1, le=25),
    severity: Optional[str] = Query(None, description="Optional severity filter (critical/high/medium/low)"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Searches ChromaDB for CVEs similar to the query."""

    service = VectorService()
    where: Optional[Dict[str, Any]] = None
    if severity:
        where = {"severity": severity.lower()}

    results = await service.search_similar_cves(query=q, n_results=n, filter_metadata=where)

    return {
        "query": q,
        "n": n,
        "severity": severity,
        "results": results,
        "viewer": {"id": current_user.id, "email": current_user.email},
    }


@router.get("/{cve_id}")
async def get_cve(
    cve_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    service = VectorService()
    item = await service.get_cve_by_id(cve_id)
    if not item:
        raise HTTPException(status_code=404, detail="CVE not found")
    return item
