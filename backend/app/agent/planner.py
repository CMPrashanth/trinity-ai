"""LLM-based attack planner using Ollama."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..services.ollama_client import OllamaClient
from ..services.ai_interface import AttackPlan, PlanStep
from ..config import settings


# System prompts for different planning modes
PLANNER_SYSTEM_PROMPT = """You are Trinity, an expert penetration testing AI agent. Your role is to generate safe, effective, and scope-compliant attack plans.

YOUR AVAILABLE ARSENAL (You MUST only use these tools):
- Active Recon: nmap (TCP/UDP/NSE), masscan, arp-scan
- Passive Recon / Auth: whois, dig, nslookup, traceroute
- Web Enum: nikto, dirb, dirbuster, wfuzz, gobuster, sslscan, whatweb, curl, wget
- Connectors & Proxies: netcat (nc), socat, proxychains
- Network Protocols: smbclient, smbmap, enum4linux, snmpwalk, snmp-check
- Vuln Scanning: sqlmap, hydra, medusa, crackmapexec

CRITICAL RULES:
1. NEVER use -T5 timing (aggressive) - maximum allowed is -T4
2. NEVER suggest destructive commands like rm -rf, format, etc.
3. ALWAYS stay within the authorized scope
4. Prioritize stealth and minimal network impact
5. Follow the reconnaissance -> enumeration -> exploitation methodology

You respond ONLY with valid JSON matching the required schema."""


QUICK_SCAN_PROMPT = """Generate a QUICK reconnaissance plan for target: {target}

Focus on:
- Fast host discovery
- Top 100 most common ports only
- Service version detection
- Quick banner grabbing

Return JSON with this exact structure:
{{
    "target": "{target}",
    "steps": [
        {{"command": "nmap command here", "description": "what this does", "rationale": "why"}}
    ],
    "reasoning": "brief explanation of the plan",
    "estimated_duration": "time estimate"
}}"""


FULL_SCAN_PROMPT = """Generate a COMPREHENSIVE penetration testing plan for target: {target}

Include:
- Full host discovery
- All TCP ports (1-65535)  
- Service version detection
- OS fingerprinting
- Safe NSE vulnerability scripts
- Banner grabbing

Return JSON with this exact structure:
{{
    "target": "{target}",
    "steps": [
        {{"command": "nmap command here", "description": "what this does", "rationale": "why"}}
    ],
    "reasoning": "brief explanation of the plan",
    "estimated_duration": "time estimate"
}}"""


STEALTH_SCAN_PROMPT = """Generate a STEALTH reconnaissance plan for target: {target}

CRITICAL: Minimize detection risk
- Use SYN scans (-sS) instead of full connect
- Use -T2 or -T3 timing (NOT -T4 or -T5)
- Randomize target order
- Limit parallel probes
- Avoid aggressive scripts

Return JSON with this exact structure:
{{
    "target": "{target}",
    "steps": [
        {{"command": "nmap command here", "description": "what this does", "rationale": "why"}}
    ],
    "reasoning": "brief explanation of the plan",
    "estimated_duration": "time estimate"
}}"""


WEB_SCAN_PROMPT = """Generate a WEB APPLICATION focused scan plan for target: {target}

Focus on:
- HTTP/HTTPS services (ports 80, 443, 8080, 8443)
- Web server identification
- HTTP-related NSE scripts (http-enum, http-headers, http-methods)
- SSL/TLS analysis

Return JSON with this exact structure:
{{
    "target": "{target}",
    "steps": [
        {{"command": "nmap command here", "description": "what this does", "rationale": "why"}}
    ],
    "reasoning": "brief explanation of the plan",
    "estimated_duration": "time estimate"
}}"""


SELF_HEAL_PROMPT = """A penetration testing command failed. Analyze the error and generate a corrected command.

FAILED COMMAND:
{failed_command}

ERROR MESSAGE:
{error_message}

CONTEXT:
{context}

Analyze what went wrong and provide a corrected approach. Return JSON:
{{
    "diagnosis": "what caused the failure",
    "corrected_command": "the fixed command",
    "explanation": "why this fix should work",
    "alternative_approach": "backup plan if fix doesn't work"
}}"""


class AttackPlanner:
    """
    LLM-based attack planner using Ollama.
    
    Implements the Planning Engine from Trinity architecture.
    """
    
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama = ollama_client or OllamaClient()
        self._prompt_templates = {
            "quick": QUICK_SCAN_PROMPT,
            "full": FULL_SCAN_PROMPT,
            "stealth": STEALTH_SCAN_PROMPT,
            "web": WEB_SCAN_PROMPT,
        }
    
    async def generate_plan(
        self,
        target: str,
        scan_profile: str = "quick",
        config: Optional[Dict[str, Any]] = None,
    ) -> AttackPlan:
        """
        Generate an attack plan using the LLM.
        
        Args:
            target: Target IP/subnet
            scan_profile: One of "quick", "full", "stealth", "web"
            config: Additional configuration options
            
        Returns:
            AttackPlan with steps and reasoning
        """
        config = config or {}
        
        # Select prompt template
        template = self._prompt_templates.get(scan_profile, QUICK_SCAN_PROMPT)
        prompt = template.format(target=target)
        
        try:
            # Call Ollama for plan generation
            response = await self.ollama.generate_json(
                prompt,
                system=PLANNER_SYSTEM_PROMPT,
                options={
                    "temperature": 0.3,  # Lower temperature for more consistent output
                    "num_predict": 1024,
                }
            )
            
            # Parse response into AttackPlan
            return self._parse_plan_response(response, target)
            
        except Exception as e:
            # Fallback to deterministic plan if LLM fails
            print(f"⚠️ LLM planning failed: {e}, using fallback plan")
            return self._fallback_plan(target, scan_profile)
    
    async def generate_heal_script(
        self,
        failed_command: str,
        error_message: str,
        context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate a corrected command using LLM self-healing.
        
        Args:
            failed_command: The command that failed
            error_message: Error output from the failure
            context: Additional context about the failure
            
        Returns:
            Dict with diagnosis and corrected_command
        """
        prompt = SELF_HEAL_PROMPT.format(
            failed_command=failed_command,
            error_message=error_message,
            context=json.dumps(context, indent=2),
        )
        
        try:
            response = await self.ollama.generate_json(
                prompt,
                system=PLANNER_SYSTEM_PROMPT,
                options={
                    "temperature": 0.2,
                    "num_predict": 512,
                }
            )
            
            return {
                "diagnosis": response.get("diagnosis", "Unknown failure"),
                "corrected_command": response.get("corrected_command", ""),
                "explanation": response.get("explanation", ""),
                "alternative_approach": response.get("alternative_approach", ""),
            }
            
        except Exception as e:
            raise RuntimeError(f"Self-heal generation failed: {e}")
    
    def _parse_plan_response(self, response: Dict[str, Any], target: str) -> AttackPlan:
        """Parse LLM response into AttackPlan model."""
        
        steps = []
        for step_data in response.get("steps", []):
            try:
                steps.append(PlanStep(
                    command=step_data.get("command", ""),
                    description=step_data.get("description", ""),
                    rationale=step_data.get("rationale"),
                ))
            except Exception:
                continue
        
        if not steps:
            # Ensure at least one step
            steps = [PlanStep(
                command=f"nmap -sV -T4 {target}",
                description="Default service scan",
            )]
        
        return AttackPlan(
            target=response.get("target", target),
            steps=steps,
            reasoning=response.get("reasoning", "LLM-generated plan"),
            estimated_duration=response.get("estimated_duration", "~5 minutes"),
        )
    
    def _fallback_plan(self, target: str, scan_profile: str) -> AttackPlan:
        """Generate a deterministic fallback plan when LLM is unavailable."""
        
        if scan_profile == "quick":
            steps = [
                PlanStep(
                    command=f"nmap -sn {target}",
                    description="Host discovery ping scan",
                    rationale="Identify live hosts before port scanning",
                ),
                PlanStep(
                    command=f"nmap -sV -T4 --top-ports 100 {target}",
                    description="Quick service detection on top 100 ports",
                    rationale="Fast identification of common services",
                ),
            ]
            duration = "~2-5 minutes"
            
        elif scan_profile == "full":
            steps = [
                PlanStep(
                    command=f"nmap -sn {target}",
                    description="Host discovery",
                    rationale="Identify all live hosts",
                ),
                PlanStep(
                    command=f"nmap -sS -sV -T4 -p- {target}",
                    description="Full port scan with service detection",
                    rationale="Comprehensive port and service enumeration",
                ),
                PlanStep(
                    command=f"nmap -sC -sV --script=vuln {target}",
                    description="Vulnerability script scan",
                    rationale="Identify known vulnerabilities",
                ),
            ]
            duration = "~30-60 minutes"
            
        elif scan_profile == "stealth":
            steps = [
                PlanStep(
                    command=f"nmap -sS -T2 -f {target}",
                    description="Fragmented stealth SYN scan",
                    rationale="Minimize detection by IDS/IPS",
                ),
                PlanStep(
                    command=f"nmap -sV -T2 --version-light {target}",
                    description="Light version detection",
                    rationale="Service identification with minimal probes",
                ),
            ]
            duration = "~15-30 minutes"
            
        elif scan_profile == "web":
            steps = [
                PlanStep(
                    command=f"nmap -sV -p 80,443,8080,8443 {target}",
                    description="Web port service detection",
                    rationale="Identify web servers",
                ),
                PlanStep(
                    command=f"nmap --script=http-enum,http-headers {target}",
                    description="Web enumeration scripts",
                    rationale="Discover web application details",
                ),
            ]
            duration = "~5-10 minutes"
            
        else:
            steps = [
                PlanStep(
                    command=f"nmap -sV -T4 {target}",
                    description="Default service scan",
                    rationale="Standard reconnaissance",
                ),
            ]
            duration = "~5 minutes"
        
        return AttackPlan(
            target=target,
            steps=steps,
            reasoning=f"Fallback {scan_profile} plan (LLM unavailable)",
            estimated_duration=duration,
        )
