"""Command executor with self-healing capabilities."""

from __future__ import annotations

import asyncio
import re
import subprocess
import xml.etree.ElementTree as ET
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from .guard import split_target_host_port, validate_scope, validate_safety


@dataclass
class ExecutionResult:
    """Result of a command execution."""
    
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    command: str
    attempt: int = 1


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent infinite retry loops."""
    
    max_failures: int = 3
    failure_count: int = 0
    is_open: bool = False
    last_failure_time: Optional[datetime] = None
    
    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        if self.failure_count >= self.max_failures:
            self.is_open = True
    
    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False
    
    def can_execute(self) -> bool:
        return not self.is_open


@dataclass
class ParsedNmapResult:
    """Parsed Nmap scan results."""
    
    hosts: List[Dict[str, Any]] = field(default_factory=list)
    ports: List[Dict[str, Any]] = field(default_factory=list)
    services: List[Dict[str, Any]] = field(default_factory=list)
    os_matches: List[Dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""


class CommandExecutor:
    """
    Executes security tools with safety validation and self-healing.
    
    Implements the Execution Engine from Trinity architecture.
    """
    
    def __init__(self, timeout: int = None, max_retries: int = None):
        self.timeout = timeout or settings.EXECUTION_TIMEOUT
        self.max_retries = max_retries or settings.MAX_RETRIES
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def _get_circuit_breaker(self, command_type: str) -> CircuitBreaker:
        """Get or create circuit breaker for command type."""
        if command_type not in self._circuit_breakers:
            self._circuit_breakers[command_type] = CircuitBreaker(
                max_failures=self.max_retries
            )
        return self._circuit_breakers[command_type]
    
    async def execute(
        self,
        command: str,
        *,
        target: Optional[str] = None,
        allowed_cidrs: Optional[List[str]] = None,
        blocked_tokens: Optional[List[str]] = None,
        validate: bool = True,
        timeout: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Execute a command with safety checks.
        
        Args:
            command: The command to execute
            target: Optional target IP for scope validation
            validate: Whether to run guard validation
            
        Returns:
            ExecutionResult with stdout/stderr and status
        """
        # Step 1: Guard validation
        if validate:
            # Scope check
            if target:
                scope_ok = False
                scope_msg = ""

                if allowed_cidrs:
                    for cidr in allowed_cidrs:
                        scope_ok, scope_msg = validate_scope(target, cidr)
                        if scope_ok:
                            break
                else:
                    scope_ok, scope_msg = validate_scope(target)

                if not scope_ok:
                    return ExecutionResult(
                        success=False,
                        stdout="",
                        stderr=f"GUARD REJECTED: {scope_msg}",
                        exit_code=-1,
                        duration_seconds=0.0,
                        command=command,
                    )
            
            # Safety check
            safety_ok, safety_msg = validate_safety(command, blocked_tokens=blocked_tokens)
            if not safety_ok:
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"GUARD REJECTED: {safety_msg}",
                    exit_code=-1,
                    duration_seconds=0.0,
                    command=command,
                )
        
        # Step 2: Circuit breaker check
        cmd_type = command.split()[0] if command else "unknown"
        breaker = self._get_circuit_breaker(cmd_type)
        
        if not breaker.can_execute():
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"CIRCUIT BREAKER OPEN: Too many failures for {cmd_type}",
                exit_code=-2,
                duration_seconds=0.0,
                command=command,
            )
        
        # Step 3: Execute command
        effective_timeout = int(timeout) if timeout is not None else int(self.timeout)
        lowered_command = (command or "").lower()

        # Basic nmap normalization to prevent invalid combinations.
        # The planner occasionally emits both SYN scan (-sS) and connect scan (-sT).
        if "nmap" in lowered_command:
            # The agent sometimes suggests non-existent flags like --timeout/--max-time.
            # We enforce timeouts at the executor level, so strip these to avoid hard failures.
            command = re.sub(r"\s--max-time(?:\s+\S+)?", "", command)
            command = re.sub(r"\s--timeout(?:\s+\S+)?", "", command)
            lowered_command = (command or "").lower()

        if "nmap" in lowered_command and " -ss" in lowered_command and " -st" in lowered_command:
            # Prefer SYN scan when both are present.
            command = command.replace(" -sT", "")
            lowered_command = (command or "").lower()
        if "nmap" in lowered_command and " -su" in lowered_command:
            # UDP scans are routinely slower; the default timeout (30s) is too aggressive.
            effective_timeout = max(effective_timeout, 180)
        if "nmap" in lowered_command and "--script=vuln" in lowered_command:
            # NSE vuln scripts + version detection can be slow; allow more time.
            effective_timeout = max(effective_timeout, 300)

        start_time = datetime.utcnow()
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout
                )
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                # Avoid propagating cancellation while cleaning up timed-out subprocesses.
                with suppress(asyncio.TimeoutError, asyncio.CancelledError, ProcessLookupError):
                    await asyncio.wait_for(process.wait(), timeout=2)
                breaker.record_failure()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"TIMEOUT: Command exceeded {effective_timeout}s",
                    exit_code=-3,
                    duration_seconds=float(effective_timeout),
                    command=command,
                )
            except asyncio.CancelledError:
                # If the event loop is being interrupted, still attempt process cleanup
                # and return a deterministic timeout-style failure object.
                with suppress(ProcessLookupError):
                    process.kill()
                with suppress(asyncio.TimeoutError, asyncio.CancelledError, ProcessLookupError):
                    await asyncio.wait_for(process.wait(), timeout=2)
                breaker.record_failure()
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="INTERRUPTED: Command execution cancelled by runtime",
                    exit_code=-5,
                    duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    command=command,
                )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            success = process.returncode == 0
            
            if success:
                breaker.record_success()
            else:
                breaker.record_failure()
            
            return ExecutionResult(
                success=success,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=process.returncode or 0,
                duration_seconds=duration,
                command=command,
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            breaker.record_failure()
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"EXECUTION ERROR: {str(e)}",
                exit_code=-4,
                duration_seconds=duration,
                command=command,
            )
    
    async def execute_nmap(
        self,
        target: str,
        *,
        ports: Optional[str] = None,
        timing: str = "-T4",
        scan_type: str = "-sV",
        scripts: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Tuple[ExecutionResult, Optional[ParsedNmapResult]]:
        """
        Execute Nmap scan with XML output parsing.
        
        Args:
            target: Target IP/subnet
            ports: Port specification (e.g., "22,80,443" or "1-1000")
            timing: Timing template (-T0 to -T4)
            scan_type: Scan type flags (e.g., "-sV", "-sS")
            scripts: NSE scripts to run
            extra_args: Additional nmap arguments
            
        Returns:
            Tuple of (ExecutionResult, ParsedNmapResult or None)
        """
        target_host, _ = split_target_host_port(target)

        # Build command
        cmd_parts = ["nmap", scan_type, timing, "-oX", "-"]
        
        if ports:
            cmd_parts.extend(["-p", ports])
        
        if scripts:
            for script in scripts:
                # Validate scripts don't contain blocked patterns
                safe, msg = validate_safety(f"--script={script}")
                if safe:
                    cmd_parts.append(f"--script={script}")
        
        if extra_args:
            cmd_parts.extend(extra_args)
        
        cmd_parts.append(target_host)
        
        command = " ".join(cmd_parts)
        
        # Execute
        result = await self.execute(command, target=target_host, validate=True)
        
        # Parse XML output if successful
        parsed = None
        if result.success and result.stdout:
            parsed = self._parse_nmap_xml(result.stdout)
        
        return result, parsed
    
    def _parse_nmap_xml(self, xml_output: str) -> ParsedNmapResult:
        """Parse Nmap XML output into structured data."""
        
        parsed = ParsedNmapResult(raw_output=xml_output)
        
        try:
            root = ET.fromstring(xml_output)
            
            for host in root.findall(".//host"):
                host_data = {}
                
                # Get IP address
                addr = host.find("address")
                if addr is not None:
                    host_data["ip"] = addr.get("addr", "")
                    host_data["addr_type"] = addr.get("addrtype", "ipv4")
                
                # Get status
                status = host.find("status")
                if status is not None:
                    host_data["state"] = status.get("state", "unknown")
                
                # Get hostname
                hostnames = host.find("hostnames")
                if hostnames is not None:
                    hostname = hostnames.find("hostname")
                    if hostname is not None:
                        host_data["hostname"] = hostname.get("name", "")
                
                parsed.hosts.append(host_data)
                
                # Get ports
                ports = host.find("ports")
                if ports is not None:
                    for port in ports.findall("port"):
                        port_data = {
                            "host": host_data.get("ip", ""),
                            "port": int(port.get("portid", 0)),
                            "protocol": port.get("protocol", "tcp"),
                        }
                        
                        state = port.find("state")
                        if state is not None:
                            port_data["state"] = state.get("state", "unknown")
                        
                        service = port.find("service")
                        if service is not None:
                            port_data["service"] = service.get("name", "")
                            port_data["product"] = service.get("product", "")
                            port_data["version"] = service.get("version", "")
                            port_data["extrainfo"] = service.get("extrainfo", "")
                            
                            # Add to services list
                            if port_data.get("service"):
                                parsed.services.append({
                                    "host": port_data["host"],
                                    "port": port_data["port"],
                                    "service": port_data["service"],
                                    "product": port_data.get("product", ""),
                                    "version": port_data.get("version", ""),
                                    "banner": port_data.get("extrainfo", ""),
                                })
                        
                        parsed.ports.append(port_data)
                
                # Get OS detection
                os_elem = host.find("os")
                if os_elem is not None:
                    for osmatch in os_elem.findall("osmatch"):
                        parsed.os_matches.append({
                            "host": host_data.get("ip", ""),
                            "name": osmatch.get("name", ""),
                            "accuracy": int(osmatch.get("accuracy", 0)),
                        })
        
        except ET.ParseError as e:
            parsed.raw_output = f"XML PARSE ERROR: {e}\n\n{xml_output}"
        
        return parsed
    
    def reset_circuit_breaker(self, command_type: str) -> None:
        """Reset circuit breaker for a command type."""
        if command_type in self._circuit_breakers:
            self._circuit_breakers[command_type] = CircuitBreaker(
                max_failures=self.max_retries
            )
