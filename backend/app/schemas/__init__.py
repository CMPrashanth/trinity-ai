"""Pydantic schemas for request/response validation"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


# ============= Authentication Schemas =============

class UserRegister(BaseModel):
    """User registration schema"""
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data"""
    email: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema"""
    id: int
    name: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============= Scan Schemas =============

class ScanProfileEnum(str, Enum):
    """Scan profile types"""
    QUICK = "quick"
    FULL = "full"
    STEALTH = "stealth"
    WEB = "web"


class ScanStatusEnum(str, Enum):
    """Scan status types"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanAdvancedOptions(BaseModel):
    """Advanced scan options"""
    enableRAG: bool = True
    circuitBreaker: bool = True
    graphMemory: bool = True
    autoHeal: bool = True


class ScanCreate(BaseModel):
    """Create new scan request"""
    target: str = Field(..., min_length=7, max_length=255)
    scanProfile: ScanProfileEnum = ScanProfileEnum.QUICK
    advancedOptions: Optional[ScanAdvancedOptions] = ScanAdvancedOptions()
    
    @validator('target')
    def validate_target(cls, v):
        """Basic target validation"""
        # Add more sophisticated validation as needed
        if not v or len(v.strip()) == 0:
            raise ValueError('Target cannot be empty')
        return v.strip()


class ScanFindings(BaseModel):
    """Scan findings summary"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class ScanResponse(BaseModel):
    """Scan response schema"""
    id: int
    scan_id: str
    target: str
    scan_type: str
    profile: str
    status: str
    findings: ScanFindings
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScanListResponse(BaseModel):
    """List of scans response"""
    scans: List[ScanResponse]
    total: int
    page: int
    page_size: int


# ============= Vulnerability Schemas =============

class SeverityEnum(str, Enum):
    """Vulnerability severity"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnStatusEnum(str, Enum):
    """Vulnerability status"""
    OPEN = "open"
    CONFIRMED = "confirmed"
    REMEDIATED = "remediated"
    FALSE_POSITIVE = "false_positive"


class VulnerabilityResponse(BaseModel):
    """Vulnerability response schema"""
    id: int
    vuln_id: str
    cve: str
    title: str
    description: Optional[str] = None
    severity: str
    cvss_score: Optional[str] = None
    target: str
    port: str
    service: Optional[str] = None
    status: str
    exploit_available: bool
    references: List[str] = []
    remediation: Optional[str] = None
    discovered_at: datetime
    
    class Config:
        from_attributes = True


class VulnerabilityListResponse(BaseModel):
    """List of vulnerabilities response"""
    vulnerabilities: List[VulnerabilityResponse]
    total: int
    page: int
    page_size: int


class VulnerabilitySeverityBreakdown(BaseModel):
    """Counts of vulnerabilities by severity"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class VulnerabilityStats(BaseModel):
    """Vulnerability statistics response"""
    total: int
    by_severity: VulnerabilitySeverityBreakdown

    class Config:
        arbitrary_types_allowed = True


# ============= Graph Schemas =============

class GraphNodeType(str, Enum):
    """Graph node types"""
    HOST = "host"
    PORT = "port"
    SERVICE = "service"
    CVE = "cve"
    VULNERABILITY = "vulnerability"


class GraphNode(BaseModel):
    """Graph node schema"""
    id: str
    label: str
    type: str
    properties: Dict = {}


class GraphEdge(BaseModel):
    """Graph edge schema"""
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    relationship: str = "CONNECTED"
    properties: Dict = {}
    
    class Config:
        populate_by_name = True


class GraphResponse(BaseModel):
    """Graph data response"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict = {}


# ============= Log Schemas =============

class LogLevelEnum(str, Enum):
    """Log levels"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class LogResponse(BaseModel):
    """Log entry response"""
    id: int
    timestamp: datetime
    level: str
    component: str
    message: str
    details: Optional[str] = None
    extra_data: Dict = {}
    
    class Config:
        from_attributes = True


class LogListResponse(BaseModel):
    """List of logs response"""
    logs: List[LogResponse]
    total: int
    page: int
    page_size: int


# ============= Dashboard Schemas =============

class DashboardActivityItem(BaseModel):
    """Dashboard activity feed item"""
    id: int
    type: str
    message: str
    target: Optional[str] = None
    timestamp: datetime
    details: Optional[str] = None


class DashboardActivityResponse(BaseModel):
    """Dashboard activity feed response"""
    activities: List[DashboardActivityItem]


# ============= Settings Schemas =============

class SettingsUpdate(BaseModel):
    """User settings update schema"""
    # Agent Settings
    llmModel: Optional[str] = None
    maxRetries: Optional[int] = Field(None, ge=1, le=10)
    executionTimeout: Optional[int] = Field(None, ge=10, le=300)
    enableSelfHealing: Optional[bool] = None
    circuitBreakerEnabled: Optional[bool] = None
    
    # Database Settings
    neo4jUri: Optional[str] = None
    chromaDbPath: Optional[str] = None
    graphHygieneEnabled: Optional[bool] = None
    
    # Scope Settings
    allowedSubnet: Optional[str] = None
    blockedCommands: Optional[str] = None
    
    # Notification Settings
    emailAlerts: Optional[bool] = None
    slackIntegration: Optional[bool] = None
    alertOnCritical: Optional[bool] = None
    alertOnCircuitBreak: Optional[bool] = None


class SettingsResponse(BaseModel):
    """User settings response"""
    # Agent Settings
    llmModel: str
    maxRetries: int
    executionTimeout: int
    enableSelfHealing: bool
    circuitBreakerEnabled: bool
    
    # Database Settings
    neo4jUri: str
    chromaDbPath: str
    graphHygieneEnabled: bool
    
    # Scope Settings
    allowedSubnet: str
    blockedCommands: List[str]
    
    # Notification Settings
    emailAlerts: bool
    slackIntegration: bool
    alertOnCritical: bool
    alertOnCircuitBreak: bool
    
    class Config:
        from_attributes = True


# ============= Dashboard/Metrics Schemas =============

class MetricsResponse(BaseModel):
    """Dashboard metrics response"""
    total_scans: int
    active_scans: int
    total_vulnerabilities: int
    critical_vulnerabilities: int
    hosts_discovered: int
    ports_discovered: int


class DashboardResponse(BaseModel):
    """Complete dashboard data"""
    metrics: MetricsResponse
    recent_scans: List[ScanResponse]
    recent_vulnerabilities: List[VulnerabilityResponse]
    vulnerability_stats: VulnerabilityStats
