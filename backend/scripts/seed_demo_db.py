"""Seed the relational DB with demo data for screenshots.

Why this exists:
- Postgres/Neo4j/Chroma data lives in Docker volumes and should not be committed.
- This script recreates a deterministic demo dataset so teammates can see the
  same scans/vulnerabilities/logs in the UI after running one command.

Usage (inside backend container or local venv):
  python -m scripts.seed_demo_db --reset
  python -m scripts.seed_demo_db --reset --with-graph

Demo login created (unless already present):
  email: demo@trinity.local
  password: demo1234
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from app.database import SessionLocal, init_db
from app.models import (
    Log,
    LogLevel,
    Scan,
    ScanProfile,
    ScanStatus,
    SeverityLevel,
    User,
    UserSettings,
    Vulnerability,
    VulnerabilityStatus,
)
from app.utils.auth import get_password_hash


@dataclass(frozen=True)
class DemoVuln:
    cve: str
    title: str
    description: str
    severity: SeverityLevel
    cvss: str
    target: str
    port: str
    service: str
    remediation: str


DEMO_USER_EMAIL = "demo@trinity.local"
DEMO_USER_PASSWORD = "demo1234"
DEMO_USER_NAME = "Trinity Demo"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_demo_user(db) -> User:
    user = db.query(User).filter(User.email == DEMO_USER_EMAIL).first()
    if user:
        return user

    user = User(
        name=DEMO_USER_NAME,
        email=DEMO_USER_EMAIL,
        hashed_password=get_password_hash(DEMO_USER_PASSWORD),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.flush()

    settings = UserSettings(
        user_id=user.id,
        allowed_subnet="10.10.0.0/24",
        blocked_commands=["-T5", "--script=dos", "rm -rf", "format"],
        circuit_breaker_enabled=True,
        enable_self_healing=True,
        execution_timeout=60,
        graph_hygiene_enabled=True,
    )
    db.add(settings)
    db.flush()

    return user


def _delete_existing_demo_data(db) -> None:
    # Delete in dependency order.
    demo_scans = db.query(Scan).filter(Scan.scan_id.like("scan-demo-%")).all()
    if not demo_scans:
        return

    scan_db_ids = [s.id for s in demo_scans]

    db.query(Vulnerability).filter(Vulnerability.scan_id.in_(scan_db_ids)).delete(synchronize_session=False)
    db.query(Log).filter(Log.scan_id.in_(scan_db_ids)).delete(synchronize_session=False)
    db.query(Scan).filter(Scan.id.in_(scan_db_ids)).delete(synchronize_session=False)


def _create_scan(
    db,
    *,
    user_id: int,
    scan_id: str,
    target: str,
    profile: ScanProfile,
    scan_type: str,
    duration_seconds: int,
    findings: dict,
) -> Scan:
    start = _utc_now() - timedelta(seconds=duration_seconds)
    end = _utc_now()

    scan = Scan(
        scan_id=scan_id,
        user_id=user_id,
        target=target,
        scan_type=scan_type,
        profile=profile,
        status=ScanStatus.COMPLETED,
        config={
            "enableRAG": True,
            "graphMemory": True,
            "autoHeal": True,
            "circuitBreaker": True,
        },
        findings=findings,
        start_time=start,
        end_time=end,
        duration=f"{duration_seconds // 60}m {duration_seconds % 60}s",
    )

    db.add(scan)
    db.flush()
    return scan


def _create_logs(db, *, scan: Scan, target_host: str) -> None:
    logs = [
        (LogLevel.INFO, "Planner", f"Scan plan created for {scan.target}", "Profile: WEB"),
        (LogLevel.INFO, "Tool", "Running nmap", f"nmap -sV -Pn -p 3000,8080 {target_host}"),
        (LogLevel.SUCCESS, "Executor", "Command completed", "exit_code=0 duration=2.1s"),
        (LogLevel.INFO, "RAG", "Searching CVEs for discovered services", "collection=cve_knowledge_base"),
        (LogLevel.SUCCESS, "Observer", "Findings persisted to database", None),
        (LogLevel.SUCCESS, "Graph", "Graph sync completed", "Network -> Host -> Port -> Service -> CVE"),
    ]

    now = _utc_now()
    for offset, (level, component, message, details) in enumerate(logs):
        db.add(
            Log(
                scan_id=scan.id,
                level=level,
                component=component,
                message=message,
                details=details,
                timestamp=now + timedelta(seconds=offset),
            )
        )


def _create_vulns(db, *, scan: Scan, vulns: Iterable[DemoVuln]) -> None:
    for idx, v in enumerate(vulns, start=1):
        db.add(
            Vulnerability(
                vuln_id=f"vuln-demo-{scan.scan_id}-{idx:02d}",
                scan_id=scan.id,
                cve=v.cve,
                title=v.title,
                description=v.description,
                severity=v.severity,
                cvss_score=v.cvss,
                target=v.target,
                port=v.port,
                service=v.service,
                status=VulnerabilityStatus.OPEN,
                exploit_available=False,
                references=["https://nvd.nist.gov"],
                remediation=v.remediation,
                discovered_at=_utc_now(),
            )
        )


def _try_seed_graph(scan_id: str) -> None:
    # Optional graph seed: best-effort only.
    try:
        from app.services.graph_service import GraphService

        graph = GraphService()
        cidr = "10.10.0.0/24"
        # Create a small lab-like topology.
        import asyncio

        async def _run() -> None:
            await graph.create_network_node(cidr=cidr, scan_id=scan_id, name=f"Lab Network {cidr}")
            for host_ip, role, ports in [
                ("10.10.0.11", "juice-shop", [(3000, "http")]),
                ("10.10.0.12", "webgoat", [(8080, "http")]),
            ]:
                await graph.create_host_node(ip=host_ip, scan_id=scan_id, role=role)
                await graph.connect_host_to_network(cidr=cidr, host_ip=host_ip, scan_id=scan_id)
                for port, service in ports:
                    await graph.create_port_node(host_ip=host_ip, port=port, service=service, scan_id=scan_id)
                    await graph.create_service_relationship(
                        host_ip=host_ip,
                        port=port,
                        service_name=service,
                        banner=None,
                        scan_id=scan_id,
                    )

        asyncio.run(_run())
    except Exception:
        # Non-fatal: graph may not be running.
        return


def seed_demo(reset: bool, with_graph: bool) -> None:
    init_db()

    db = SessionLocal()
    try:
        user = _ensure_demo_user(db)

        if reset:
            _delete_existing_demo_data(db)

        # Two demo scans that match your lab targets.
        scan1 = _create_scan(
            db,
            user_id=user.id,
            scan_id="scan-demo-juice-shop",
            target="10.10.0.11:3000",
            profile=ScanProfile.WEB,
            scan_type="web",
            duration_seconds=42,
            findings={"critical": 1, "high": 1, "medium": 0, "low": 0, "info": 0},
        )
        _create_logs(db, scan=scan1, target_host="10.10.0.11")
        _create_vulns(
            db,
            scan=scan1,
            vulns=[
                DemoVuln(
                    cve="CVE-2023-44487",
                    title="HTTP/2 Rapid Reset (DoS risk)",
                    description="HTTP/2 Rapid Reset technique impacting certain HTTP/2 implementations.",
                    severity=SeverityLevel.HIGH,
                    cvss="7.5",
                    target="10.10.0.11",
                    port="3000",
                    service="http",
                    remediation="Update reverse proxy / HTTP stack; apply vendor mitigations; rate-limit requests.",
                ),
                DemoVuln(
                    cve="CVE-2024-3094",
                    title="XZ Utils supply-chain backdoor (awareness)",
                    description="XZ Utils supply-chain backdoor in certain releases affecting liblzma usage paths.",
                    severity=SeverityLevel.CRITICAL,
                    cvss="10.0",
                    target="10.10.0.11",
                    port="3000",
                    service="http",
                    remediation="Inventory affected packages; remove compromised versions; rotate keys; rebuild from trusted sources.",
                ),
            ],
        )

        scan2 = _create_scan(
            db,
            user_id=user.id,
            scan_id="scan-demo-webgoat",
            target="10.10.0.12:8080",
            profile=ScanProfile.WEB,
            scan_type="web",
            duration_seconds=55,
            findings={"critical": 1, "high": 0, "medium": 1, "low": 0, "info": 0},
        )
        _create_logs(db, scan=scan2, target_host="10.10.0.12")
        _create_vulns(
            db,
            scan=scan2,
            vulns=[
                DemoVuln(
                    cve="CVE-2021-44228",
                    title="Log4Shell (Log4j2) RCE risk (awareness)",
                    description="Apache Log4j2 remote code execution risk via JNDI message lookups under certain configurations.",
                    severity=SeverityLevel.CRITICAL,
                    cvss="10.0",
                    target="10.10.0.12",
                    port="8080",
                    service="http",
                    remediation="Upgrade Log4j2, disable JNDI lookups, and verify runtime mitigations.",
                ),
                DemoVuln(
                    cve="CVE-2014-0160",
                    title="Heartbleed (OpenSSL) info disclosure (awareness)",
                    description="OpenSSL Heartbleed information disclosure that can leak memory contents from affected systems.",
                    severity=SeverityLevel.HIGH,
                    cvss="7.5",
                    target="10.10.0.12",
                    port="8080",
                    service="http",
                    remediation="Upgrade OpenSSL and rotate affected secrets/certificates.",
                ),
            ],
        )

        db.commit()

        if with_graph:
            _try_seed_graph(scan_id=scan2.scan_id)

        print("✅ Seeded demo DB data successfully")
        print(f"   Login: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}")

    finally:
        db.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Trinity demo data into the relational DB")
    parser.add_argument("--reset", action="store_true", help="Delete existing demo scans/vulns/logs before seeding")
    parser.add_argument("--with-graph", action="store_true", help="Best-effort seed of Neo4j graph nodes/edges")

    args = parser.parse_args(argv)
    seed_demo(reset=args.reset, with_graph=args.with_graph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
