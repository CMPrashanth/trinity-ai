"""Seed ChromaDB with a baseline + lab-tagged CVEs.

- Adds curated demo CVEs if the collection is empty.
- Fetches a small set of real CVEs from NVD using keywordSearch for the lab apps.

Usage (from repo root / trinity-ai):
  docker exec trinity_backend python scripts/seed_lab_cves.py

Notes:
- Uses the configured NVD API key if present (optional).
- Designed to keep the seed small so it is quick and repeatable.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# When executed as a script (python scripts/seed_lab_cves.py), Python sets
# sys.path[0] to /app/scripts, so we need to add /app to import the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.cve_feed_service import CVEFeedService
from app.services.vector_service import VectorService


LAB_KEYWORDS: dict[str, list[str]] = {
    "webgoat": ["spring framework", "spring boot", "apache tomcat", "log4j"],
    "juiceshop": ["node.js", "express", "angular"],
}


async def main() -> None:
    vector_service = VectorService()
    if not vector_service.collection:
        raise SystemExit("ChromaDB collection not available")

    count_before = vector_service.collection.count()
    print(f"count_before={count_before}")

    if count_before == 0:
        added = await vector_service.seed_demo_cves(reset=False)
        print(f"seed_demo_added={added}")

    feed = CVEFeedService(vector_service=vector_service)

    total = 0
    for app, keywords in LAB_KEYWORDS.items():
        records = await feed.search_by_keywords(
            keywords,
            per_keyword=6,
            max_total=30,
            extra_metadata={"source": "nvd", "seed": "lab", "app": app},
        )
        if records:
            await vector_service.bulk_add_cves(records)
        print(f"{app}_records={len(records)}")
        total += len(records)

    print(f"records_upserted_estimate={total}")
    print(f"count_after={vector_service.collection.count()}")


if __name__ == "__main__":
    asyncio.run(main())
