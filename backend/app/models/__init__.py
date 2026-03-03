"""Database models"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from ..database import Base


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    scans = relationship("Scan", back_populates="user")
    settings = relationship("UserSettings", back_populates="user", uselist=False)


class ScanStatus(enum.Enum):
    """Scan status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanProfile(enum.Enum):
    """Scan profile types"""
    QUICK = "quick"
    FULL = "full"
    STEALTH = "stealth"
    WEB = "web"


class Scan(Base):
    """Scan model"""
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "scan-001"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    target = Column(String(255), nullable=False)
    scan_type = Column(String(100), nullable=False)
    profile = Column(SQLEnum(ScanProfile), default=ScanProfile.QUICK)
    status = Column(SQLEnum(ScanStatus), default=ScanStatus.QUEUED, index=True)
    
    # Scan configuration
    config = Column(JSON, default={})  # Stores advanced options
    
    # Results summary
    findings = Column(JSON, default={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0})
    
    # Timing
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(String(50), nullable=True)  # e.g., "23m 45s"
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="scans")
    vulnerabilities = relationship("Vulnerability", back_populates="scan")
    logs = relationship("Log", back_populates="scan")


class SeverityLevel(enum.Enum):
    """Vulnerability severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityStatus(enum.Enum):
    """Vulnerability status"""
    OPEN = "open"
    CONFIRMED = "confirmed"
    REMEDIATED = "remediated"
    FALSE_POSITIVE = "false_positive"


class Vulnerability(Base):
    """Vulnerability findings model"""
    __tablename__ = "vulnerabilities"
    
    id = Column(Integer, primary_key=True, index=True)
    vuln_id = Column(String(50), unique=True, index=True, nullable=False)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)
    
    cve = Column(String(50), index=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    severity = Column(SQLEnum(SeverityLevel), index=True, nullable=False)
    cvss_score = Column(String(10), nullable=True)
    
    target = Column(String(255), nullable=False)
    port = Column(String(50), nullable=False)
    service = Column(String(100), nullable=True)
    
    status = Column(SQLEnum(VulnerabilityStatus), default=VulnerabilityStatus.OPEN)
    
    # Additional details
    exploit_available = Column(Boolean, default=False)
    references = Column(JSON, default=[])
    remediation = Column(Text, nullable=True)
    
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    scan = relationship("Scan", back_populates="vulnerabilities")


class LogLevel(enum.Enum):
    """Log severity levels"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class Log(Base):
    """Activity log model"""
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    level = Column(SQLEnum(LogLevel), default=LogLevel.INFO, index=True)
    component = Column(String(100), nullable=False, index=True)  # Planner, Executor, Observer, etc.
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    
    # Additional data (renamed from 'metadata' to avoid SQLAlchemy conflict)
    extra_data = Column(JSON, default={})
    
    # Relationships
    scan = relationship("Scan", back_populates="logs")


class UserSettings(Base):
    """User-specific settings model"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Agent Settings
    llm_model = Column(String(100), default="llama3.1:8b-instruct")
    max_retries = Column(Integer, default=3)
    execution_timeout = Column(Integer, default=30)
    enable_self_healing = Column(Boolean, default=True)
    circuit_breaker_enabled = Column(Boolean, default=True)
    
    # Database Settings
    neo4j_uri = Column(String(255), default="bolt://localhost:7687")
    chroma_db_path = Column(String(255), default="./chroma_db")
    graph_hygiene_enabled = Column(Boolean, default=True)
    
    # Scope Settings
    allowed_subnet = Column(String(255), default="192.168.1.0/24")
    blocked_commands = Column(JSON, default=["-T5", "--script=dos", "rm -rf", "format"])
    
    # Notification Settings
    email_alerts = Column(Boolean, default=True)
    slack_integration = Column(Boolean, default=False)
    alert_on_critical = Column(Boolean, default=True)
    alert_on_circuit_break = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="settings")
