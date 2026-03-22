"""
Trinity AI - Real implementation of the neuro-symbolic penetration testing agent.

This module implements the full Trinity architecture:
- Planner: LLM-based attack planning via Ollama
- Guard: Pydantic/regex-based scope and safety validation
- Executor: Command execution with circuit breaker
- Observer: Result parsing and graph persistence
"""

from __future__ import annotations

import json
import re
import shlex
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

try:
    from ..services.langchain_service import LangChainService
except Exception:  # pragma: no cover
    LangChainService = None

try:
    from ..services.langgraph_workflow import LangGraphSecurityWorkflow
except Exception:  # pragma: no cover
    LangGraphSecurityWorkflow = None
from .guard import split_target_host_port, validate_scope, validate_safety
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
        self.langchain_service = None
        self.langgraph_workflow = None

        if settings.USE_LANGCHAIN and LangChainService is not None:
            try:
                self.langchain_service = LangChainService(
                    model=self.llm_model,
                    base_url=settings.OLLAMA_BASE_URL,
                )
            except Exception as e:
                print(f"⚠️ LangChain disabled due to initialization error: {e}")

        if settings.USE_LANGGRAPH and LangGraphSecurityWorkflow is not None:
            try:
                self.langgraph_workflow = LangGraphSecurityWorkflow(
                    vector_service=self.vector_service,
                    langchain_service=self.langchain_service,
                )
            except Exception as e:
                print(f"⚠️ LangGraph disabled due to initialization error: {e}")
        
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
                self._log(
                    "debug",
                    "Metrics",
                    "guard_decision",
                    details=json.dumps(
                        {
                            "event": "guard_decision",
                            "decision": "approved",
                            "reason": "safe",
                            "command": step.command,
                            "description": step.description,
                        }
                    ),
                )
            else:
                self._log("warning", "Guard", f"Blocked: {step.description}", safety_msg)
                self._log(
                    "debug",
                    "Metrics",
                    "guard_decision",
                    details=json.dumps(
                        {
                            "event": "guard_decision",
                            "decision": "rejected",
                            "reason": safety_msg or "blocked",
                            "command": step.command,
                            "description": step.description,
                        }
                    ),
                )
        
        if not validated_steps:
            self._log("error", "Guard", "No valid steps in plan after safety check")
            raise ValueError("All plan steps were blocked by safety guard")
        
        plan.steps = validated_steps

        if self.langchain_service is not None:
            try:
                adjustment = await self.langchain_service.plan_adjustments(
                    target=target,
                    scan_profile=scan_profile,
                    existing_reasoning=plan.reasoning,
                )
                if adjustment:
                    plan.reasoning = f"{plan.reasoning}\n\nLangChain Guidance:\n{adjustment}"
            except Exception as e:
                self._log("warning", "LangChain", f"Plan enhancement skipped: {e}")

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

        target_host, target_port = split_target_host_port(attack_plan.target)
        
        for i, step in enumerate(attack_plan.steps):
            self._log("info", "Executor", f"Step {i+1}/{len(attack_plan.steps)}: {step.description}")

            command_to_run = self._normalize_command_for_target(
                step.command,
                target_host=target_host,
                target_port=target_port,
            )
            tool_name = (command_to_run.strip().split() or ["unknown"])[0]

            if command_to_run != step.command:
                self._log(
                    "debug",
                    "Tool",
                    f"Normalized command for target {attack_plan.target}",
                    details=f"before: {step.command}\nafter:  {command_to_run}",
                )

            self._log("info", "Tool", f"Running {tool_name}", details=command_to_run)
            
            # Execute with potential self-healing
            result = await self._execute_with_healing(
                command_to_run,
                target_host,
                config,
            )
            
            if result.success:
                self._log("success", "Executor", f"Step {i+1} completed successfully")
                self._log(
                    "debug",
                    "Tool",
                    f"{tool_name} exit={result.exit_code} duration={result.duration_seconds:.2f}s",
                    details=(result.stderr or "").strip()[:500] or None,
                )
                
                # Parse Nmap output if applicable
                if "nmap" in command_to_run.lower():
                    hosts, ports, services = self._parse_nmap_output(
                        result.stdout,
                        default_host=target_host,
                    )
                    all_hosts.extend(hosts)
                    all_ports.extend(ports)
                    all_services.extend(services)
            else:
                self._log("warning", "Executor", f"Step {i+1} failed", result.stderr)
                self._log(
                    "warning",
                    "Tool",
                    f"{tool_name} failed exit={result.exit_code}",
                    details=(result.stderr or "").strip()[:500] or None,
                )
        
        # Analyze for vulnerabilities using RAG
        if all_services:
            if self.langgraph_workflow is not None:
                self._log("info", "LangGraph", "Running workflow for CVE enrichment")
                try:
                    workflow_result = await self.langgraph_workflow.run(
                        target=attack_plan.target,
                        scan_profile=config.get("scan_profile", "quick"),
                        services=all_services,
                    )
                    graph_vulns = workflow_result.get("vulnerabilities", [])
                    all_vulns.extend(self._to_vulnerability_models(graph_vulns))
                    self._log("success", "LangGraph", f"Workflow produced {len(graph_vulns)} candidates")
                except Exception as e:
                    self._log("warning", "LangGraph", f"Workflow failed, falling back to RAG: {e}")
                    vulns = await self._analyze_services_for_vulns(all_services)
                    all_vulns.extend(vulns)
            else:
                self._log("info", "Observer", "Analyzing services for vulnerabilities")
                vulns = await self._analyze_services_for_vulns(all_services)
                all_vulns.extend(vulns)
        
        # Deduplicate hosts. Derive hosts even when Nmap doesn't populate host headers.
        derived_hosts = set(all_hosts)
        derived_hosts.update(p.host for p in all_ports if getattr(p, "host", None))
        derived_hosts.update(s.host for s in all_services if getattr(s, "host", None))
        if not derived_hosts and target_host:
            derived_hosts.add(target_host)
        unique_hosts = list(derived_hosts)
        
        self._log("success", "Observer", 
                  f"Scan complete: {len(unique_hosts)} hosts, {len(all_ports)} ports, {len(all_vulns)} vulnerabilities")
        
        return ScanResult(
            hosts_discovered=unique_hosts,
            ports_discovered=all_ports,
            services_identified=all_services,
            vulnerabilities_found=all_vulns,
            execution_logs=self._execution_logs.copy(),
        )

    _IP_WITH_PORT_TOKEN = re.compile(r"\b(?P<ip>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d{1,5})\b")
    _IPV4_TOKEN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?\b")
    _CIDR_TOKEN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}\b")
    _NMAP_FLAG_HINT = re.compile(r"(?:^|\s)(?:-s[STUV]|-sC|-A|-O|-Pn|--script\b|-oN\b|-oX\b)")

    def _first_token(self, command: str) -> str:
        try:
            parts = shlex.split(command)
        except Exception:
            parts = (command or "").strip().split()
        return parts[0] if parts else ""

    def _command_mentions_target(self, command: str) -> bool:
        if not command:
            return False
        return bool(self._IPV4_TOKEN.search(command) or self._CIDR_TOKEN.search(command))

    def _normalize_command_for_target(self, command: str, *, target_host: str, target_port: Optional[int]) -> str:
        """Normalize commands when the user provides an IPv4 target with a port.

        Host-only tools like `nmap`, `dig`, and `nslookup` must not receive `ip:port`.
        HTTP tools like `curl` can keep `host:port`.
        """

        cmd = (command or "").strip()
        if not cmd:
            return cmd

        # Repair common LLM failure mode: emits only flags (e.g., "-sT -p 80")
        # which the shell treats as an illegal option. If it looks like nmap flags,
        # prepend "nmap".
        if cmd.startswith("-") and self._NMAP_FLAG_HINT.search(cmd):
            cmd = f"nmap {cmd}"

        lowered = cmd.lower().lstrip()
        host_only_tools = (
            "nmap",
            "dig",
            "nslookup",
            "whois",
            "traceroute",
        )

        if lowered.startswith(host_only_tools):
            cmd = self._IP_WITH_PORT_TOKEN.sub(lambda m: m.group("ip"), cmd)
            if target_host and target_port is not None:
                cmd = cmd.replace(f"{target_host}:{target_port}", target_host)

            # If the command still doesn't mention any host/subnet, append the target host.
            # This fixes plans that forget to include the target argument.
            if target_host and not self._command_mentions_target(cmd):
                cmd = f"{cmd} {target_host}"

        return cmd
    
    async def _execute_with_healing(
        self,
        command: str,
        target: str,
        config: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute command with self-healing on failure."""

        result = await self.executor.execute(
            command,
            target=target,
            allowed_cidrs=config.get("allowed_cidrs"),
            blocked_tokens=config.get("blocked_commands"),
        )

        self._log(
            "debug",
            "Metrics",
            "command_attempt",
            details=json.dumps(
                {
                    "event": "command_attempt",
                    "attempt": 1,
                    "phase": "initial",
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "duration_seconds": result.duration_seconds,
                    "command": command,
                }
            ),
        )
        
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
                diagnosis = (healed.get("diagnosis") or "").strip()
                detail_lines = []
                if diagnosis:
                    detail_lines.append(f"diagnosis: {diagnosis}")
                detail_lines.append(f"corrected_command: {corrected_cmd}")
                self._log(
                    "info",
                    "SelfHeal",
                    "Trying corrected command",
                    "\n".join(detail_lines)[:800] or None,
                )
                
                # Validate corrected command
                safety_ok, _ = validate_safety(corrected_cmd)
                if safety_ok:
                    healed_result = await self.executor.execute(
                        corrected_cmd,
                        target=target,
                        allowed_cidrs=config.get("allowed_cidrs"),
                        blocked_tokens=config.get("blocked_commands"),
                    )
                    self._log(
                        "debug",
                        "Metrics",
                        "command_attempt",
                        details=json.dumps(
                            {
                                "event": "command_attempt",
                                "attempt": attempts + 2,
                                "phase": "healed",
                                "success": healed_result.success,
                                "exit_code": healed_result.exit_code,
                                "duration_seconds": healed_result.duration_seconds,
                                "command": corrected_cmd,
                            }
                        ),
                    )
                    return healed_result
                else:
                    self._log("warning", "SelfHeal", "Corrected command blocked by guard")
            
        except Exception as e:
            self._log("error", "SelfHeal", f"Self-heal failed: {e}")
        
        return result
    
    def _parse_nmap_output(
        self,
        output: str,
        *,
        default_host: Optional[str] = None,
    ) -> tuple[List[str], List[PortDiscovery], List[ServiceIdentification]]:
        """Parse Nmap output (handles both XML and text formats)."""

        def _normalize_service_name(service: str, port: int) -> str:
            svc = (service or "").strip().lower().rstrip("?;,")

            preferred: Optional[str] = None
            if port in {443, 8443}:
                preferred = "https"
            elif port in {80, 3000, 8080}:
                preferred = "http"

            if not preferred:
                return svc or "unknown"

            if svc in {"http", "https"}:
                return svc

            if svc in {"unknown", "ppp", "http-proxy", "tcpwrapped"}:
                return preferred

            if preferred == "http" and svc in {"http-alt", "webcache"}:
                return "http"
            if preferred == "https" and svc in {"ssl/http", "https-alt", "ssl", "tls"}:
                return "https"

            return svc or preferred
        
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
                    host_value = (p.get("host") or default_host or "").strip()
                    port_value = int(p.get("port") or 0)
                    raw_service_value = (p.get("service") or "").strip() or "unknown"
                    if not host_value or port_value <= 0:
                        continue

                    service_value = _normalize_service_name(raw_service_value, port_value)
                    ports.append(PortDiscovery(
                        host=host_value,
                        port=port_value,
                        service=service_value,
                        version=p.get("version"),
                    ))
            
            for s in parsed.services:
                host_value = (s.get("host") or default_host or "").strip()
                port_value = int(s.get("port") or 0)
                raw_service_value = (s.get("service") or "").strip()
                if not host_value or not raw_service_value:
                    continue

                service_value = _normalize_service_name(raw_service_value, port_value) if port_value > 0 else (raw_service_value or "unknown")
                services.append(ServiceIdentification(
                    host=host_value,
                    service=service_value,
                    banner=s.get("banner"),
                    metadata={
                        "port": port_value,
                        "nmap_service": raw_service_value,
                        "product": s.get("product", ""),
                        "version": s.get("version", ""),
                    },
                ))
        else:
            # Basic text parsing fallback
            current_host = (default_host or "").strip()
            ip_pattern = re.compile(r"Nmap scan report for (\d+\.\d+\.\d+\.\d+)")
            port_pattern = re.compile(r"(?P<port>\d+)/(?:tcp|udp)\s+open\s+(?P<service>\S+)")

            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue

                host_match = ip_pattern.search(line)
                if host_match:
                    current_host = host_match.group(1).strip()
                    if current_host:
                        hosts.append(current_host)
                    continue

                port_match = port_pattern.search(line)
                if port_match:
                    if not current_host:
                        continue
                    port_num = int(port_match.group("port"))
                    raw_service_name = port_match.group("service").strip() or "unknown"
                    service_name = _normalize_service_name(raw_service_name, port_num)
                    ports.append(PortDiscovery(
                        host=current_host,
                        port=port_num,
                        service=service_name,
                    ))
                    services.append(ServiceIdentification(
                        host=current_host,
                        service=service_name,
                        metadata={"port": port_num, "nmap_service": raw_service_name},
                    ))
        
        return hosts, ports, services
    
    async def _analyze_services_for_vulns(
        self,
        services: List[ServiceIdentification],
    ) -> List[VulnerabilityFinding]:
        """Use RAG to find potential vulnerabilities for discovered services."""
        
        vulnerabilities: List[VulnerabilityFinding] = []
        
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
                    cve_id = cve.get("cve_id")
                    if not cve_id:
                        continue

                    metadata = cve.get("metadata") if isinstance(cve.get("metadata"), dict) else {}
                    severity = (metadata.get("severity") or cve.get("severity") or "medium")

                    cvss_value = metadata.get("cvss") or cve.get("cvss")
                    cvss: Optional[float] = None
                    try:
                        if cvss_value is not None and cvss_value != "":
                            cvss = float(cvss_value)
                    except Exception:
                        cvss = None

                    description = cve.get("description")
                    title = (
                        metadata.get("title")
                        or cve.get("title")
                        or (str(description).split(" - ", 1)[0] if description else None)
                        or f"Potential vulnerability in {svc.service}"
                    )

                    vulnerabilities.append(VulnerabilityFinding(
                        cve=cve_id,
                        title=title,
                        severity=severity,
                        cvss=cvss,
                        target=svc.host,
                        port=str(svc.metadata.get("port", "")),
                        service=svc.service,
                        description=description,
                        references=cve.get("references", []),
                        metadata={
                            "source": "rag",
                            "similarity_score": cve.get("similarity_score"),
                        },
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

    def _to_vulnerability_models(
        self,
        raw_vulnerabilities: List[Dict[str, Any]],
    ) -> List[VulnerabilityFinding]:
        """Convert workflow dictionaries into validated VulnerabilityFinding models."""
        normalized: List[VulnerabilityFinding] = []
        allowed_severity = {"critical", "high", "medium", "low", "info"}

        for vuln in raw_vulnerabilities:
            cve_id = str(vuln.get("cve") or "").strip()
            if not cve_id.startswith("CVE-"):
                continue

            severity = str(vuln.get("severity") or "medium").lower()
            if severity not in allowed_severity:
                severity = "medium"

            references = vuln.get("references", [])
            if not isinstance(references, list):
                references = []

            normalized.append(VulnerabilityFinding(
                cve=cve_id,
                title=str(vuln.get("title") or f"Potential vulnerability ({cve_id})"),
                severity=severity,
                cvss=vuln.get("cvss"),
                target=str(vuln.get("target") or "unknown"),
                port=str(vuln.get("port") or "unknown"),
                service=vuln.get("service"),
                description=vuln.get("description"),
                remediation=vuln.get("remediation"),
                exploit_available=bool(vuln.get("exploit_available", False)),
                references=references,
                metadata=vuln.get("metadata") if isinstance(vuln.get("metadata"), dict) else {},
            ))

        return normalized
    
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
            scope_cidr = getattr(settings, "SCOPE_SUBNET", "")
            if scope_cidr:
                await self.graph_service.create_network_node(
                    cidr=scope_cidr,
                    scan_id=scan_id,
                    name=f"Lab Network {scope_cidr}",
                )

            # Create host nodes
            for host_ip in scan_result.hosts_discovered:
                await self.graph_service.create_host_node(
                    ip=host_ip,
                    scan_id=scan_id,
                )

                if scope_cidr:
                    await self.graph_service.connect_host_to_network(
                        cidr=scope_cidr,
                        host_ip=host_ip,
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

                if port.service:
                    await self.graph_service.create_service_relationship(
                        host_ip=port.host,
                        port=port.port,
                        service_name=port.service,
                        banner=port.version,
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
