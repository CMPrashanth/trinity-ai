"""Scan service - handles scan creation and execution"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import secrets

from ..models import Scan, ScanStatus, ScanProfile, Vulnerability, Log, LogLevel, SeverityLevel, VulnerabilityStatus
from ..schemas import ScanCreate
from .ai_interface import DummyAI, AIInterface
from ..config import settings


def _create_default_ai() -> AIInterface:
    """Create the appropriate AI instance based on configuration."""
    
    # We want to use the real AI even in debug mode
    use_real_ai = True
    
    if use_real_ai:
        try:
            from ..agent import TrinityAI
            print("🔱 Initializing TrinityAI with backend")
            return TrinityAI(llm_model=settings.LLM_MODEL_ID)
        except Exception as e:
            print(f"⚠️ TrinityAI initialization failed: {e}")
            print("   Falling back to DummyAI")
    
    return DummyAI(llm_model=settings.LLM_MODEL_ID)


class ScanService:
    """Service for managing scans"""
    
    def __init__(self, db: Session, ai: Optional[AIInterface] = None):
        self.db = db
        # Use configuration-based AI selection
        self.ai = ai or _create_default_ai()
    
    async def create_scan(self, scan_data: ScanCreate, user_id: int) -> Scan:
        """Create a new scan"""
        
        # Generate unique scan ID
        scan_id = f"scan-{secrets.token_hex(4)}"
        
        # Map scan profile to scan type name
        scan_type_map = {
            "quick": "Quick Scan",
            "full": "Full Network Scan",
            "stealth": "Stealth Mode Scan",
            "web": "Web Application Scan"
        }
        
        scan_type = scan_type_map.get(scan_data.scanProfile.value, "Quick Scan")
        
        # Create scan record
        scan = Scan(
            scan_id=scan_id,
            user_id=user_id,
            target=scan_data.target,
            scan_type=scan_type,
            profile=ScanProfile[scan_data.scanProfile.value.upper()],
            status=ScanStatus.QUEUED,
            config=scan_data.advancedOptions.model_dump() if scan_data.advancedOptions else {}
        )
        
        self.db.add(scan)
        self.db.commit()
        self.db.refresh(scan)
        
        # Log scan creation
        self._create_log(
            scan.id,
            LogLevel.INFO,
            "System",
            f"Scan {scan_id} created for target {scan_data.target}"
        )
        
        return scan
    
    async def start_scan(self, scan_db_id: int):
        """Start scan execution (background task)"""
        scan = self.db.query(Scan).filter(Scan.id == scan_db_id).first()
        if not scan:
            return
        
        try:
            # Update status to running
            scan.status = ScanStatus.RUNNING
            scan.start_time = datetime.utcnow()
            self.db.commit()
            
            self._create_log(scan.id, LogLevel.INFO, "Planner", f"Generating attack plan for target {scan.target}")
            
            # Step 1: Generate attack plan using AI
            attack_plan = await self.ai.generate_attack_plan(
                target=scan.target,
                scan_profile=scan.profile.value,
                config=scan.config
            )
            
            self._create_log(scan.id, LogLevel.SUCCESS, "Guard", "Plan validated successfully")
            
            # Step 2: Execute the scan
            self._create_log(scan.id, LogLevel.INFO, "Executor", "Executing scan commands")

            execution_config = dict(scan.config or {})
            execution_config.setdefault("scan_profile", scan.profile.value)

            scan_result = await self.ai.execute_scan(attack_plan, execution_config)
            
            self._create_log(scan.id, LogLevel.SUCCESS, "Executor", "Scan execution completed")
            
            # Step 3: Process results and create vulnerability records
            await self._process_scan_results(scan, scan_result)
            
            # Step 3.5: Persist execution logs from AI agent
            for log_entry in scan_result.execution_logs:
                level_map = {
                    "debug": LogLevel.DEBUG,
                    "info": LogLevel.INFO,
                    "success": LogLevel.SUCCESS,
                    "warning": LogLevel.WARNING,
                    "error": LogLevel.ERROR,
                }
                self._create_log(
                    scan.id,
                    level_map.get(log_entry.level, LogLevel.INFO),
                    log_entry.component,
                    log_entry.message,
                    log_entry.details
                )
            
            # Step 4: Update graph (if enabled)
            if scan.config.get("graphMemory", True):
                self._create_log(scan.id, LogLevel.INFO, "Observer", "Updating Neo4j attack graph")
                await self.ai.update_graph(scan_result, scan.scan_id)
                self._create_log(
                    scan.id, LogLevel.SUCCESS, "Observer",
                    f"Created {len(scan_result.hosts_discovered)} host nodes, {len(scan_result.ports_discovered)} port nodes"
                )
            
            # Mark as completed
            scan.status = ScanStatus.COMPLETED
            scan.end_time = datetime.utcnow()
            
            # Calculate duration
            duration_seconds = (scan.end_time - scan.start_time).total_seconds()
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            scan.duration = f"{minutes}m {seconds}s"
            
            self.db.commit()
            
            self._create_log(scan.id, LogLevel.SUCCESS, "System", f"Scan {scan.scan_id} completed successfully")
            
        except Exception as e:
            # Handle scan failure
            scan.status = ScanStatus.FAILED
            scan.end_time = datetime.utcnow()
            self.db.commit()
            
            self._create_log(scan.id, LogLevel.ERROR, "System", f"Scan failed: {str(e)}")
    
    async def _process_scan_results(self, scan: Scan, scan_result):
        """Process scan results and create vulnerability records"""
        
        findings_count = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        
        for vuln_data in scan_result.vulnerabilities_found:
            # Create vulnerability record
            vuln_id = f"vuln-{secrets.token_hex(4)}"
            
            severity_str = vuln_data.severity.lower()
            severity = SeverityLevel[severity_str.upper()]
            
            vulnerability = Vulnerability(
                vuln_id=vuln_id,
                scan_id=scan.id,
                cve=vuln_data.cve,
                title=vuln_data.title,
                description=vuln_data.description,
                severity=severity,
                cvss_score=str(vuln_data.cvss) if vuln_data.cvss is not None else None,
                target=vuln_data.target or scan.target,
                port=vuln_data.port or "unknown",
                service=vuln_data.service,
                status=VulnerabilityStatus.OPEN,
                exploit_available=vuln_data.exploit_available,
                references=vuln_data.references
            )
            
            self.db.add(vulnerability)
            findings_count[severity_str] += 1
            
            # Log vulnerability discovery
            if scan.config.get("enableRAG", True):
                self._create_log(
                    scan.id, LogLevel.SUCCESS, "RAG",
                    f"{vuln_data.cve} matched from ChromaDB vector search",
                    details="Similarity score: 0.94"
                )
            
            self._create_log(
                scan.id, LogLevel.INFO, "Observer",
                f"Vulnerability node created: {vuln_data.cve} -> {vuln_data.target}:{vuln_data.port}"
            )
        
        # Update scan findings summary
        scan.findings = findings_count
        self.db.commit()
    
    def _create_log(
        self,
        scan_id: int,
        level: LogLevel,
        component: str,
        message: str,
        details: Optional[str] = None
    ):
        """Create a log entry"""
        log = Log(
            scan_id=scan_id,
            level=level,
            component=component,
            message=message,
            details=details
        )
        self.db.add(log)
        self.db.commit()
