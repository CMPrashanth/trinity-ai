"""NVD CVE feed synchronization service for ChromaDB knowledge base."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

from ..config import settings
from .vector_service import VectorService


class CVEFeedService:
    """Fetches CVE updates from NVD and upserts them into ChromaDB."""

    def __init__(self, vector_service: VectorService | None = None):
        self.vector_service = vector_service or VectorService()
        self.state_path = Path("/app/cve_sync_state.json") if Path("/app").exists() else Path("cve_sync_state.json")

    async def sync_latest(self, max_records: int = 5000) -> Dict[str, Any]:
        """Sync latest CVEs from NVD and store in vector DB."""
        since = self._load_last_sync()
        now = datetime.now(timezone.utc)

        collected: List[Dict[str, Any]] = []
        start_index = 0
        page_size = min(settings.NVD_RESULTS_PER_PAGE, 2000)

        headers = {}
        if settings.NVD_API_KEY:
            headers["apiKey"] = settings.NVD_API_KEY

        async with httpx.AsyncClient(timeout=45.0) as client:
            while len(collected) < max_records:
                params = {
                    "resultsPerPage": page_size,
                    "startIndex": start_index,
                    "lastModStartDate": since.isoformat().replace("+00:00", "Z"),
                    "lastModEndDate": now.isoformat().replace("+00:00", "Z"),
                }

                response = await client.get(settings.NVD_BASE_URL, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()

                vulnerabilities = payload.get("vulnerabilities", [])
                if not vulnerabilities:
                    break

                normalized = [self._normalize_record(item) for item in vulnerabilities]
                normalized = [item for item in normalized if item is not None]
                collected.extend(normalized)

                total_results = int(payload.get("totalResults", 0))
                start_index += page_size
                if start_index >= total_results:
                    break

        if collected:
            await self.vector_service.bulk_add_cves(collected)

        self._save_last_sync(now)

        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for item in collected:
            sev = str(item.get("metadata", {}).get("severity", "unknown")).lower()
            severities[sev if sev in severities else "unknown"] += 1

        return {
            "status": "success",
            "new_cves": len(collected),
            "since": since.isoformat(),
            "until": now.isoformat(),
            "severity_breakdown": severities,
        }

    async def search_by_keywords(
        self,
        keywords: List[str],
        *,
        per_keyword: int = 20,
        max_total: int = 200,
        extra_metadata: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Fetch CVEs from NVD using keywordSearch and return normalized records.

        This is used for lab/demo seeding so we can populate Chroma with *real* CVEs
        without inventing IDs.
        """

        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()

        headers: Dict[str, str] = {}
        if settings.NVD_API_KEY:
            headers["apiKey"] = settings.NVD_API_KEY

        extra_metadata = dict(extra_metadata or {})

        async with httpx.AsyncClient(timeout=45.0) as client:
            for kw in [k.strip() for k in keywords if str(k).strip()]:
                if len(normalized) >= max_total:
                    break

                params = {
                    "resultsPerPage": min(int(per_keyword), 2000),
                    "startIndex": 0,
                    "keywordSearch": kw,
                }

                response = await client.get(settings.NVD_BASE_URL, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()

                vulnerabilities = payload.get("vulnerabilities", [])
                for item in vulnerabilities:
                    if len(normalized) >= max_total:
                        break

                    record = self._normalize_record(item)
                    if not record:
                        continue

                    cve_id = record.get("cve_id")
                    if not cve_id or cve_id in seen:
                        continue

                    seen.add(cve_id)

                    md = dict(record.get("metadata", {}) or {})
                    md.update(extra_metadata)
                    md.setdefault("seed", "lab")
                    md.setdefault("keyword", kw)
                    record["metadata"] = md

                    normalized.append(record)

        return normalized

    def _normalize_record(self, item: Dict[str, Any]) -> Dict[str, Any] | None:
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            return None

        descriptions = cve.get("descriptions", [])
        description = next((d.get("value") for d in descriptions if d.get("lang") == "en"), "")

        metrics = cve.get("metrics", {})
        cvss, severity = self._extract_cvss(metrics)

        references = [ref.get("url") for ref in cve.get("references", []) if ref.get("url")]

        published = cve.get("published")
        modified = cve.get("lastModified")

        metadata = {
            "severity": severity,
            "cvss": cvss,
            "published": published,
            "modified": modified,
            "title": cve_id,
            "references": references,
            "source": "nvd",
        }

        return {
            "cve_id": cve_id,
            "description": description or f"NVD entry for {cve_id}",
            "metadata": metadata,
        }

    @staticmethod
    def _extract_cvss(metrics: Dict[str, Any]) -> tuple[float | None, str]:
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(key, [])
            if not entries:
                continue

            metric = entries[0]
            data = metric.get("cvssData", {})
            score = data.get("baseScore")
            severity = data.get("baseSeverity") or metric.get("baseSeverity")

            try:
                if score is not None:
                    return float(score), str(severity or "unknown").lower()
            except (TypeError, ValueError):
                continue

        return None, "unknown"

    def _load_last_sync(self) -> datetime:
        if self.state_path.exists():
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
                value = payload.get("last_sync")
                if value:
                    return datetime.fromisoformat(value)
            except Exception:
                pass

        # Default to a conservative recent window on first run.
        return datetime.now(timezone.utc) - timedelta(days=7)

    def _save_last_sync(self, synced_at: datetime) -> None:
        data = {"last_sync": synced_at.isoformat()}
        self.state_path.write_text(json.dumps(data), encoding="utf-8")
