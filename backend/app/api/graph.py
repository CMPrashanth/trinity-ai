"""Graph visualization API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from urllib.parse import urlparse

from ..database import get_db
from ..schemas import GraphResponse
from ..models import User, Scan, Vulnerability
from ..utils.auth import get_current_user
from ..services.graph_service import GraphService

router = APIRouter()


def _normalize_host_key(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None

    value = raw_value.strip().lower()
    if not value:
        return None

    if "://" in value:
        parsed = urlparse(value)
        if parsed.hostname:
            return parsed.hostname.lower()

    if "/" in value:
        value = value.split("/", 1)[0]

    if ":" in value:
        value = value.split(":", 1)[0]

    return value.strip() or None


def _safe_node_id_fragment(raw_value: Optional[str]) -> str:
    value = (raw_value or "unknown").strip().lower()
    sanitized = "".join(ch if ch.isalnum() else "-" for ch in value)
    return sanitized.strip("-") or "unknown"


@router.get("/graph", response_model=GraphResponse)
async def get_graph_data(
    scan_id: Optional[str] = None,
    scan_db_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get attack graph data from Neo4j"""
    graph_service = GraphService()

    # Backwards compatibility: the UI already uses `scan_id=<db primary key>` in places (e.g., Logs).
    # If the provided scan_id looks numeric, treat it as a DB id.
    if scan_db_id is None and scan_id and scan_id.isdigit():
        scan_db_id = int(scan_id)
        scan_id = None

    scan = None
    if scan_db_id is not None:
        scan = (
            db.query(Scan)
            .filter(Scan.id == scan_db_id, Scan.user_id == current_user.id)
            .first()
        )
        if not scan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scan not found",
            )
        scan_id = scan.scan_id
    elif scan_id:
        scan = (
            db.query(Scan)
            .filter(Scan.scan_id == scan_id, Scan.user_id == current_user.id)
            .first()
        )
        if not scan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scan not found",
            )
    
    try:
        graph_data = await graph_service.get_graph(scan_id)

        if scan:
            nodes = graph_data.setdefault("nodes", [])
            edges = graph_data.setdefault("edges", [])

            # Populate ID tracker with existing Neo4j nodes (by ID)
            existing_node_ids = {str(node.get("id")) for node in nodes}
            existing_edge_ids = {
                (
                    str(edge.get("from")),
                    str(edge.get("to")),
                    str(edge.get("relationship", "CONNECTED")),
                )
                for edge in edges
            }
            
            # Map normalized CVE ID to Node ID for O(1) lookup to avoid O(N*M) loop
            cve_id_to_node_id = {}
            for node in nodes:
                node_type = str(node.get("type", "")).lower()
                if node_type == "cve":
                    props = node.get("properties") or {}
                    cve_val = props.get("cve_id") or props.get("cve") or node.get("label")
                    if cve_val:
                        normalized = str(cve_val).strip().upper()
                        cve_id_to_node_id[normalized] = str(node.get("id"))

            # Host lookup map
            host_node_by_key = {}
            for node in nodes:
                if str(node.get("type", "")).lower() != "host":
                    continue
                props = node.get("properties") or {}
                host_key_candidates = [
                    props.get("ip"),
                    props.get("host"),
                    node.get("label"),
                    props.get("label"),
                    props.get("name"),
                ]
                for candidate in host_key_candidates:
                    key = _normalize_host_key(str(candidate) if candidate is not None else None)
                    if key:
                        host_node_by_key[key] = str(node.get("id"))

            vulnerabilities = db.query(Vulnerability).filter(Vulnerability.scan_id == scan.id).all()

            for vuln in vulnerabilities:
                severity_value = vuln.severity.value if hasattr(vuln.severity, "value") else str(vuln.severity)

                vuln_node_id = f"sql-vuln-{vuln.id}"
                
                # Determine best display label
                display_label = vuln.title
                if not display_label or "vuln-" in display_label.lower():
                    if vuln.cve and "vuln-" not in vuln.cve.lower():
                        display_label = f"{vuln.cve}"
                    else:
                        display_label = vuln.title or vuln.vuln_id

                if vuln_node_id not in existing_node_ids:
                    nodes.append(
                        {
                            "id": vuln_node_id,
                            "label": display_label,
                            "type": "vulnerability",
                            "properties": {
                                "vuln_id": vuln.vuln_id,
                                "severity": severity_value,
                                "title": display_label, # Use derived label as title for frontend priority
                                "original_title": vuln.title,
                                "target": vuln.target,
                                "port": vuln.port,
                                "service": vuln.service,
                                "scan_id": scan.scan_id,
                                "source": "sql",
                            },
                        }
                    )
                    existing_node_ids.add(vuln_node_id)

                # Link to CVE node (existing or new)
                target_cve_id = None
                vuln_cve_norm = vuln.cve.strip().upper() if vuln.cve else None

                if vuln_cve_norm and vuln_cve_norm in cve_id_to_node_id:
                    # Use existing CVE node
                    target_cve_id = cve_id_to_node_id[vuln_cve_norm]
                elif vuln.cve:
                    # Create new CVE node
                    cve_clean = _safe_node_id_fragment(vuln.cve)
                    cve_node_id = f"sql-cve-{cve_clean}"
                    
                    if cve_node_id not in existing_node_ids:
                        nodes.append(
                            {
                                "id": cve_node_id,
                                "label": vuln.cve,
                                "type": "cve",  # Explicitly set type to "cve"
                                "properties": {
                                    "cve_id": vuln.cve,
                                    "severity": severity_value,
                                    "cvss": vuln.cvss_score,
                                    "title": vuln.title,
                                    "scan_id": scan.scan_id,
                                    "source": "sql",
                                },
                            }
                        )
                        existing_node_ids.add(cve_node_id)
                        # Register in map to prevent future duplicates in this loop
                        if vuln_cve_norm:
                            cve_id_to_node_id[vuln_cve_norm] = cve_node_id
                    
                    target_cve_id = cve_node_id

                if target_cve_id:
                    vuln_to_cve_edge = (vuln_node_id, target_cve_id, "HAS_CVE")
                    if vuln_to_cve_edge not in existing_edge_ids:
                        edges.append({"from": vuln_node_id, "to": target_cve_id, "relationship": "HAS_CVE", "properties": {"source": "sql"}})
                        existing_edge_ids.add(vuln_to_cve_edge)

                host_key = _normalize_host_key(vuln.target)
                host_node_id = host_node_by_key.get(host_key or "")

                if not host_node_id:
                    host_node_id = f"sql-host-{_safe_node_id_fragment(vuln.target)}"
                    if host_node_id not in existing_node_ids:
                        nodes.append(
                            {
                                "id": host_node_id,
                                "label": vuln.target,
                                "type": "host",
                                "properties": {
                                    "ip": vuln.target,
                                    "label": vuln.target,
                                    "scan_id": scan.scan_id,
                                    "source": "sql",
                                },
                            }
                        )
                        existing_node_ids.add(host_node_id)
                    if host_key:
                        host_node_by_key[host_key] = host_node_id

                host_to_vuln_edge = (host_node_id, vuln_node_id, "VULNERABLE_TO")
                if host_to_vuln_edge not in existing_edge_ids:
                    edges.append({"from": host_node_id, "to": vuln_node_id, "relationship": "VULNERABLE_TO", "properties": {"source": "sql"}})
                    existing_edge_ids.add(host_to_vuln_edge)

            graph_data["metadata"] = {
                **(graph_data.get("metadata") or {}),
                "scan_id": scan.scan_id,
                "sql_vulnerability_count": len(vulnerabilities),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }

        return graph_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve graph data: {str(e)}"
        )


@router.get("/graph/nodes/{node_id}")
async def get_node_details(
    node_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific node"""
    graph_service = GraphService()
    
    try:
        node_data = await graph_service.get_node_details(node_id)
        
        if not node_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node not found"
            )
        
        return node_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node data: {str(e)}"
        )


@router.get("/graph/paths")
async def get_attack_paths(
    source: Optional[str] = None,
    target: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get attack paths between nodes"""
    graph_service = GraphService()
    
    try:
        paths = await graph_service.find_paths(source, target)
        return {"paths": paths}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find paths: {str(e)}"
        )


@router.delete("/graph", status_code=status.HTTP_204_NO_CONTENT)
async def clear_graph(
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Clear graph data (graph hygiene)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    graph_service = GraphService()
    
    try:
        await graph_service.clear_graph(scan_id)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear graph: {str(e)}"
        )


@router.post("/graph/export")
async def export_graph(
    format: str = Query("json", regex="^(json|graphml|cypher)$"),
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Export graph data in various formats"""
    graph_service = GraphService()
    
    try:
        exported_data = await graph_service.export_graph(format, scan_id)
        return exported_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export graph: {str(e)}"
        )
