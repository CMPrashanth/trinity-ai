"""
Trinity AI - Real implementation of the neuro-symbolic penetration testing agent.

This module implements the full Trinity architecture:
- Planner: LLM-based attack planning via Ollama
- Guard: Pydantic/regex-based scope and safety validation
- Executor: Command execution with circuit breaker
- Observer: Result parsing and graph persistence
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import settings
from ..services.ai_interface import (
    AIInterface,
    AttackPlan,
    ExecutionLogEntry,
    PortDiscovery,
    ScanResult,
    ServiceIdentification,
    VulnerabilityFinding,
    SelfHealError,
    GraphSyncError,
)
from ..services.ollama_client import OllamaClient
from ..services.graph_service import GraphService
from ..services.vector_service import VectorService
from .guard import validate_scope, validate_safety
from .executor import CommandExecutor, ExecutionResult
from .planner import AttackPlanner


class TrinityAI(AIInterface):
    """
    Production implementation of the Trinity neuro-symbolic agent.
    
    Integrates:
    - OllamaClient for LLM reasoning (WhiteRabbitNeo model)
    - Pydantic Guard for scope/safety validation
    - CommandExecutor with circuit breaker for self-healing
    - Neo4j GraphService for attack path persistence
    - ChromaDB VectorService for CVE RAG lookups
    """
    
    def __init__(
        self,
        llm_model: Optional[str] = None,
        *,
        graph_service: Optional[GraphService] = None,
        vector_service: Optional[VectorService] = None,
    ):
        self.llm_model = llm_model or settings.LLM_MODEL_ID
        
        # Initialize components
        self.ollama = OllamaClient(model=self.llm_model)
        self.planner = AttackPlanner(ollama_client=self.ollama)
        self.executor = CommandExecutor(
            timeout=settings.EXECUTION_TIMEOUT,
            max_retries=settings.MAX_RETRIES,
        )
        self.graph_service = graph_service or GraphService()
        self.vector_service = vector_service or VectorService()
        
        # Runtime state
        self._execution_logs: List[ExecutionLogEntry] = []
        self._heal_attempts: Dict[str, int] = {}
        
        print(f"🔱 TrinityAI initialized with model: {self.llm_model}")
    
    def _log(
        self,
        level: str,
        component: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Add an entry to execution logs."""
        self._execution_logs.append(ExecutionLogEntry(
            level=level,
            component=component,
            message=message,
            details=details,
            timestamp=datetime.utcnow(),
        ))
    
    async def generate_attack_plan(
        self,
        target: str,
        scan_profile: str,
        config: Dict[str, Any],
    ) -> AttackPlan:
        """
        Generate an attack plan using LLM with guard validation.
        
        The planning flow:
        1. Validate target is in scope
        2. Query Ollama for attack plan
        3. Validate each command in plan against safety rules
        4. Return sanitized plan
        """
        self._execution_logs = []  # Reset logs for new scan
        self._log("info", "Planner", f"Generating {scan_profile} plan for {target}")
        
        # Step 1: Scope validation using allowed_cidrs from config
        allowed_cidrs = config.get("allowed_cidrs", [])
        scope_ok = False
        scope_msg = ""
        
        if not allowed_cidrs:
            # No CIDRs specified, use default scope
            scope_ok, scope_msg = validate_scope(target)
        else:
            # Check if target is in any of the allowed CIDRs
            for cidr in allowed_cidrs:
                scope_ok, scope_msg = validate_scope(target, cidr)
                if scope_ok:
                    break
        
        if not scope_ok:
            self._log("error", "Guard", f"Scope violation: {scope_msg}")
            raise ValueError(f"Target out of scope: {scope_msg}")
        
        self._log("success", "Guard", f"Target {target} within authorized scope")
        
        # Step 2: Generate plan via LLM
        try:
            plan = await self.planner.generate_plan(target, scan_profile, config)
            self._log("success", "Planner", f"Generated plan with {len(plan.steps)} steps")
        except Exception as e:
            self._log("error", "Planner", f"Plan generation failed: {e}")
            raise
        
        # Step 3: Validate each command
        validated_steps = []
        for step in plan.steps:
            safety_ok, safety_msg = validate_safety(step.command)
            if safety_ok:
                validated_steps.append(step)
                self._log("info", "Guard", f"Approved: {step.description}")
            else:
                self._log("warning", "Guard", f"Blocked: {step.description}", safety_msg)
        
        if not validated_steps:
            self._log("error", "Guard", "No valid steps in plan after safety check")
            raise ValueError("All plan steps were blocked by safety guard")
        
        plan.steps = validated_steps
        return plan
    
    async def execute_scan(
        self,
        attack_plan: AttackPlan,
        config: Dict[str, Any],
    ) -> ScanResult:
        """
        Execute the attack plan with self-healing.
        
        The execution flow:
        1. Execute each step sequentially
        2. On failure, attempt self-healing via LLM
        3. Parse outputs and aggregate results
        4. Persist to Neo4j graph
        """
        self._log("info", "Executor", f"Starting execution of {len(attack_plan.steps)} steps")
        
        all_hosts: List[str] = []
        all_ports: List[PortDiscovery] = []
        all_services: List[ServiceIdentification] = []
        all_vulns: List[VulnerabilityFinding] = []
        
        for i, step in enumerate(attack_plan.steps):
            self._log("info", "Executor", f"Step {i+1}/{len(attack_plan.steps)}: {step.description}")
            
            # Execute with potential self-healing
            result = await self._execute_with_healing(
                step.command,
                attack_plan.target,
                config,
            )
            
            if result.success:
                self._log("success", "Executor", f"Step {i+1} completed successfully")
                
                # Parse Nmap output if applicable
                if "nmap" in step.command.lower():
                    hosts, ports, services = self._parse_nmap_output(result.stdout)
                    all_hosts.extend(hosts)
                    all_ports.extend(ports)
                    all_services.extend(services)
            else:
                self._log("warning", "Executor", f"Step {i+1} failed", result.stderr)
        
        # Analyze for vulnerabilities using RAG
        if all_services:
            self._log("info", "Observer", "Analyzing services for vulnerabilities")
            vulns = await self._analyze_services_for_vulns(all_services)
            all_vulns.extend(vulns)
        
        # Deduplicate hosts
        unique_hosts = list(set(all_hosts))
        
        self._log("success", "Observer", 
                  f"Scan complete: {len(unique_hosts)} hosts, {len(all_ports)} ports, {len(all_vulns)} vulnerabilities")
        
        return ScanResult(
            hosts_discovered=unique_hosts,
            ports_discovered=all_ports,
            services_identified=all_services,
            vulnerabilities_found=all_vulns,
            execution_logs=self._execution_logs.copy(),
        )
    
    async def _execute_with_healing(
        self,
        command: str,
        target: str,
        config: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute command with self-healing on failure."""
        
        result = await self.executor.execute(command, target=target)
        
        if result.success:
            return result
        
        # Attempt self-healing if enabled
        if not settings.ENABLE_SELF_HEALING:
            return result
        
        # Track heal attempts
        cmd_key = command[:50]
        attempts = self._heal_attempts.get(cmd_key, 0)
        
        if attempts >= settings.MAX_RETRIES:
            self._log("error", "SelfHeal", f"Max heal attempts reached for command")
            return result
        
        self._heal_attempts[cmd_key] = attempts + 1
        self._log("info", "SelfHeal", f"Attempting self-heal (attempt {attempts + 1})")
        
        try:
            healed = await self.planner.generate_heal_script(
                failed_command=command,
                error_message=result.stderr,
                context={"target": target, "config": config},
            )
            
            corrected_cmd = healed.get("corrected_command", "")
            if corrected_cmd:
                self._log("info", "SelfHeal", f"Trying corrected command", healed.get("diagnosis"))
                
                # Validate corrected command
                safety_ok, _ = validate_safety(corrected_cmd)
                if safety_ok:
                    return await self.executor.execute(corrected_cmd, target=target)
                else:
                    self._log("warning", "SelfHeal", "Corrected command blocked by guard")
            
        except Exception as e:
            self._log("error", "SelfHeal", f"Self-heal failed: {e}")
        
        return result
    
    def _parse_nmap_output(
        self,
        output: str,
    ) -> tuple[List[str], List[PortDiscovery], List[ServiceIdentification]]:
        """Parse Nmap output (handles both XML and text formats)."""
        
        hosts = []
        ports = []
        services = []
        
        # Try XML parsing first via executor
        if output.strip().startswith("<?xml"):
            from .executor import CommandExecutor
            executor = CommandExecutor()
            parsed = executor._parse_nmap_xml(output)
            
            for h in parsed.hosts:
                if h.get("ip") and h.get("state") == "up":
                    hosts.append(h["ip"])
            
            for p in parsed.ports:
                if p.get("state") == "open":
                    ports.append(PortDiscovery(
                        host=p.get("host", ""),
                        port=p.get("port", 0),
                        service=p.get("service", "unknown"),
                        version=p.get("version"),
                    ))
            
            for s in parsed.services:
                services.append(ServiceIdentification(
                    host=s.get("host", ""),
                    service=s.get("service", ""),
                    banner=s.get("banner"),
                    metadata={
                        "product": s.get("product", ""),
                        "version": s.get("version", ""),
                    },
                ))
        else:
            # Basic text parsing fallback
            import re
            
            # Find hosts
            ip_pattern = r"Nmap scan report for (\d+\.\d+\.\d+\.\d+)"
            for match in re.finditer(ip_pattern, output):
                hosts.append(match.group(1))
            
            # Find open ports
            port_pattern = r"(\d+)/(\w+)\s+open\s+(\S+)"
            current_host = hosts[-1] if hosts else ""
            for match in re.finditer(port_pattern, output):
                port_num = int(match.group(1))
                service_name = match.group(3)
                ports.append(PortDiscovery(
                    host=current_host,
                    port=port_num,
                    service=service_name,
                ))
                services.append(ServiceIdentification(
                    host=current_host,
                    service=service_name,
                ))
        
        return hosts, ports, services
    
    async def _analyze_services_for_vulns(
        self,
        services: List[ServiceIdentification],
    ) -> List[VulnerabilityFinding]:
        """Use RAG to find potential vulnerabilities for discovered services."""
        
        vulnerabilities = []
        
        for svc in services:
            # Build search query from service info
            query = f"{svc.service}"
            if svc.metadata.get("product"):
                query += f" {svc.metadata['product']}"
            if svc.metadata.get("version"):
                query += f" {svc.metadata['version']}"
            
            # Search ChromaDB for similar CVEs
            try:
                cves = await self.vector_service.search_similar_cves(
                    query=query,
                    n_results=3,
                )
                
                for cve in cves:
                    if cve.get("cve_id"):
                        vulnerabilities.append(VulnerabilityFinding(
                            cve=cve["cve_id"],
                            title=cve.get("title", f"Potential vulnerability in {svc.service}"),
                            severity=cve.get("severity", "medium"),
                            cvss=cve.get("cvss"),
                            target=svc.host,
                            port=str(svc.metadata.get("port", "")),
                            service=svc.service,
                            description=cve.get("description"),
                            references=cve.get("references", []),
                        ))
            except Exception as e:
                self._log("warning", "RAG", f"CVE lookup failed for {svc.service}: {e}")
        
        return vulnerabilities
    
    async def self_heal_script(
        self,
        failed_script: str,
        error_message: str,
        context: Dict[str, Any],
    ) -> str:
        """Use LLM to generate a corrected script."""
        
        try:
            healed = await self.planner.generate_heal_script(
                failed_command=failed_script,
                error_message=error_message,
                context=context,
            )
            return healed.get("corrected_command", failed_script)
        except Exception as e:
            raise SelfHealError(f"Could not generate heal script: {e}")
    
    async def analyze_vulnerability(
        self,
        service_info: Dict[str, Any],
        use_rag: bool = True,
    ) -> List[Dict[str, Any]]:
        """Analyze service for vulnerabilities using RAG."""
        
        if not use_rag:
            return []
        
        query = f"{service_info.get('service', '')} {service_info.get('version', '')}"
        
        try:
            return await self.vector_service.search_similar_cves(
                query=query,
                n_results=5,
            )
        except Exception:
            return []
    
    async def update_graph(
        self,
        scan_result: ScanResult,
        scan_id: str,
    ) -> bool:
        """Persist scan results to Neo4j graph database."""
        
        try:
            # Create host nodes
            for host_ip in scan_result.hosts_discovered:
                await self.graph_service.create_host_node(
                    ip=host_ip,
                    scan_id=scan_id,
                )
            
            # Create port and service relationships
            for port in scan_result.ports_discovered:
                await self.graph_service.create_port_node(
                    host_ip=port.host,
                    port=port.port,
                    service=port.service,
                    version=port.version,
                    scan_id=scan_id,
                )
            
            # Create vulnerability relationships
            for vuln in scan_result.vulnerabilities_found:
                await self.graph_service.create_vulnerability_node(
                    host_ip=vuln.target,
                    cve_id=vuln.cve,
                    severity=vuln.severity,
                    cvss=vuln.cvss,
                    title=vuln.title,
                    scan_id=scan_id,
                )
            
            self._log("success", "Graph", f"Persisted {len(scan_result.hosts_discovered)} hosts to Neo4j")
            return True
            
        except Exception as e:
            self._log("error", "Graph", f"Graph update failed: {e}")
            raise GraphSyncError(f"Failed to update Neo4j graph: {e}")
