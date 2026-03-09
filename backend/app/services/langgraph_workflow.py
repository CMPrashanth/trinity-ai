"""LangGraph workflow for service-to-CVE enrichment and remediation analysis."""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from .ai_interface import ServiceIdentification


class WorkflowState(TypedDict, total=False):
    target: str
    scan_profile: str
    services: List[ServiceIdentification]
    cve_candidates: List[Dict[str, Any]]
    vulnerabilities: List[Dict[str, Any]]
    remediation_summary: str


class LangGraphSecurityWorkflow:
    """Coordinates CVE enrichment and remediation suggestion through a graph flow."""

    def __init__(self, vector_service, langchain_service: Any | None = None):
        self.vector_service = vector_service
        self.langchain_service = langchain_service
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(WorkflowState)

        workflow.add_node("recon", self._recon_node)
        workflow.add_node("enrich", self._enrichment_node)
        workflow.add_node("remediate", self._remediation_node)

        workflow.set_entry_point("recon")
        workflow.add_edge("recon", "enrich")
        workflow.add_edge("enrich", "remediate")
        workflow.add_edge("remediate", END)

        return workflow.compile()

    async def _recon_node(self, state: WorkflowState) -> WorkflowState:
        # Recon node is intentionally lightweight because discovery already happened in Trinity executor.
        services = state.get("services", [])
        return {"services": services, "cve_candidates": []}

    async def _enrichment_node(self, state: WorkflowState) -> WorkflowState:
        services = state.get("services", [])
        cve_candidates: List[Dict[str, Any]] = []

        for svc in services:
            query = svc.service
            if svc.metadata.get("product"):
                query += f" {svc.metadata['product']}"
            if svc.metadata.get("version"):
                query += f" {svc.metadata['version']}"

            results = await self.vector_service.search_similar_cves(query=query, n_results=3)
            for item in results:
                cve_candidates.append({
                    "service": svc.service,
                    "target": svc.host,
                    "port": str(svc.metadata.get("port", "")),
                    "cve_id": item.get("cve_id"),
                    "description": item.get("description"),
                    "metadata": item.get("metadata", {}),
                    "similarity_score": item.get("similarity_score", 0.0),
                })

        vulnerabilities: List[Dict[str, Any]] = []
        for cve in cve_candidates:
            metadata = cve.get("metadata", {})
            vulnerabilities.append({
                "cve": cve.get("cve_id") or "CVE-2000-0000",
                "title": metadata.get("title") or f"Potential vulnerability in {cve.get('service', 'service')}",
                "severity": (metadata.get("severity") or "medium").lower(),
                "cvss": self._safe_cvss(metadata.get("cvss")),
                "target": cve.get("target", "unknown"),
                "port": cve.get("port", ""),
                "service": cve.get("service"),
                "description": cve.get("description"),
                "references": metadata.get("references", []),
                "metadata": {
                    "similarity_score": cve.get("similarity_score", 0.0),
                    "source": "langgraph+rag",
                },
            })

        return {
            "cve_candidates": cve_candidates,
            "vulnerabilities": vulnerabilities,
        }

    async def _remediation_node(self, state: WorkflowState) -> WorkflowState:
        vulnerabilities = state.get("vulnerabilities", [])
        remediation_summary = "No remediation actions required."

        if vulnerabilities and self.langchain_service is not None:
            remediation_summary = await self.langchain_service.summarize_remediation(vulnerabilities)

        for vuln in vulnerabilities:
            vuln["remediation"] = remediation_summary

        return {
            "vulnerabilities": vulnerabilities,
            "remediation_summary": remediation_summary,
        }

    async def run(
        self,
        target: str,
        scan_profile: str,
        services: List[ServiceIdentification],
    ) -> Dict[str, Any]:
        """Execute the LangGraph pipeline and return enriched vulnerability output."""
        initial_state: WorkflowState = {
            "target": target,
            "scan_profile": scan_profile,
            "services": services,
            "cve_candidates": [],
            "vulnerabilities": [],
            "remediation_summary": "",
        }
        return await self.graph.ainvoke(initial_state)

    @staticmethod
    def _safe_cvss(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            cvss = float(value)
            if 0.0 <= cvss <= 10.0:
                return cvss
        except (TypeError, ValueError):
            return None
        return None
