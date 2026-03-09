"""User settings API routes"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SettingsUpdate, SettingsResponse
from ..models import User, UserSettings
from ..utils.auth import get_current_user

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if not settings:
        # Create default settings if they don't exist
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    # Convert blocked_commands from JSON to list if it's a string
    response_data = {
        "llmModel": settings.llm_model,
        "maxRetries": settings.max_retries,
        "executionTimeout": settings.execution_timeout,
        "enableSelfHealing": settings.enable_self_healing,
        "circuitBreakerEnabled": settings.circuit_breaker_enabled,
        "neo4jUri": settings.neo4j_uri,
        "chromaDbPath": settings.chroma_db_path,
        "graphHygieneEnabled": settings.graph_hygiene_enabled,
        "allowedSubnet": settings.allowed_subnet,
        "blockedCommands": settings.blocked_commands if isinstance(settings.blocked_commands, list) else [],
        "emailAlerts": settings.email_alerts,
        "slackIntegration": settings.slack_integration,
        "alertOnCritical": settings.alert_on_critical,
        "alertOnCircuitBreak": settings.alert_on_circuit_break,
    }
    
    return response_data


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    settings_data: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
    
    # Update only provided fields
    update_data = settings_data.model_dump(exclude_unset=True)
    
    # Map camelCase to snake_case
    field_mapping = {
        "llmModel": "llm_model",
        "maxRetries": "max_retries",
        "executionTimeout": "execution_timeout",
        "enableSelfHealing": "enable_self_healing",
        "circuitBreakerEnabled": "circuit_breaker_enabled",
        "neo4jUri": "neo4j_uri",
        "chromaDbPath": "chroma_db_path",
        "graphHygieneEnabled": "graph_hygiene_enabled",
        "allowedSubnet": "allowed_subnet",
        "blockedCommands": "blocked_commands",
        "emailAlerts": "email_alerts",
        "slackIntegration": "slack_integration",
        "alertOnCritical": "alert_on_critical",
        "alertOnCircuitBreak": "alert_on_circuit_break",
    }
    
    for camel_key, value in update_data.items():
        snake_key = field_mapping.get(camel_key, camel_key)
        
        # Handle blocked_commands conversion from string to list
        if snake_key == "blocked_commands" and isinstance(value, str):
            value = [cmd.strip() for cmd in value.split(",")]
        
        if hasattr(settings, snake_key):
            setattr(settings, snake_key, value)
    
    db.commit()
    db.refresh(settings)
    
    # Return updated settings
    response_data = {
        "llmModel": settings.llm_model,
        "maxRetries": settings.max_retries,
        "executionTimeout": settings.execution_timeout,
        "enableSelfHealing": settings.enable_self_healing,
        "circuitBreakerEnabled": settings.circuit_breaker_enabled,
        "neo4jUri": settings.neo4j_uri,
        "chromaDbPath": settings.chroma_db_path,
        "graphHygieneEnabled": settings.graph_hygiene_enabled,
        "allowedSubnet": settings.allowed_subnet,
        "blockedCommands": settings.blocked_commands if isinstance(settings.blocked_commands, list) else [],
        "emailAlerts": settings.email_alerts,
        "slackIntegration": settings.slack_integration,
        "alertOnCritical": settings.alert_on_critical,
        "alertOnCircuitBreak": settings.alert_on_circuit_break,
    }
    
    return response_data


@router.post("/settings/reset")
async def reset_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset settings to default values"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if settings:
        db.delete(settings)
        db.commit()
    
    # Create new default settings
    default_settings = UserSettings(user_id=current_user.id)
    db.add(default_settings)
    db.commit()
    db.refresh(default_settings)
    
    return {"message": "Settings reset to default values"}


@router.post("/settings/cve/sync-now")
async def trigger_cve_sync(
    current_user: User = Depends(get_current_user),
):
    """Queue an on-demand CVE feed synchronization task."""
    try:
        from ..tasks.cve_tasks import sync_cve_feed

        task = sync_cve_feed.delay()
        return {
            "message": "CVE synchronization task queued",
            "taskId": task.id,
            "queuedBy": current_user.email,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue CVE sync task: {exc}",
        )
