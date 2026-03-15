"""User settings API routes"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import httpx

from ..database import get_db
from ..schemas import SettingsUpdate, SettingsResponse
from ..models import User, UserSettings
from ..utils.auth import get_current_user
from ..config import settings as app_settings

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user settings"""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if not user_settings:
        # Create default settings if they don't exist
        user_settings = UserSettings(user_id=current_user.id, allowed_subnet=app_settings.SCOPE_SUBNET)
        db.add(user_settings)
        db.commit()
        db.refresh(user_settings)
    
    # Convert blocked_commands from JSON to list if it's a string
    response_data = {
        "llmModel": user_settings.llm_model,
        "maxRetries": user_settings.max_retries,
        "executionTimeout": user_settings.execution_timeout,
        "enableSelfHealing": user_settings.enable_self_healing,
        "circuitBreakerEnabled": user_settings.circuit_breaker_enabled,
        "neo4jUri": user_settings.neo4j_uri,
        "chromaDbPath": user_settings.chroma_db_path,
        "graphHygieneEnabled": user_settings.graph_hygiene_enabled,
        "allowedSubnet": user_settings.allowed_subnet,
        "blockedCommands": user_settings.blocked_commands if isinstance(user_settings.blocked_commands, list) else [],
        "emailAlerts": user_settings.email_alerts,
        "slackIntegration": user_settings.slack_integration,
        "alertOnCritical": user_settings.alert_on_critical,
        "alertOnCircuitBreak": user_settings.alert_on_circuit_break,
    }
    
    return response_data


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    settings_data: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if not user_settings:
        user_settings = UserSettings(user_id=current_user.id, allowed_subnet=app_settings.SCOPE_SUBNET)
        db.add(user_settings)
    
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
        
        if hasattr(user_settings, snake_key):
            setattr(user_settings, snake_key, value)
    
    db.commit()
    db.refresh(user_settings)
    
    # Return updated settings
    response_data = {
        "llmModel": user_settings.llm_model,
        "maxRetries": user_settings.max_retries,
        "executionTimeout": user_settings.execution_timeout,
        "enableSelfHealing": user_settings.enable_self_healing,
        "circuitBreakerEnabled": user_settings.circuit_breaker_enabled,
        "neo4jUri": user_settings.neo4j_uri,
        "chromaDbPath": user_settings.chroma_db_path,
        "graphHygieneEnabled": user_settings.graph_hygiene_enabled,
        "allowedSubnet": user_settings.allowed_subnet,
        "blockedCommands": user_settings.blocked_commands if isinstance(user_settings.blocked_commands, list) else [],
        "emailAlerts": user_settings.email_alerts,
        "slackIntegration": user_settings.slack_integration,
        "alertOnCritical": user_settings.alert_on_critical,
        "alertOnCircuitBreak": user_settings.alert_on_circuit_break,
    }
    
    return response_data


@router.post("/settings/reset")
async def reset_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset settings to default values"""
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    
    if user_settings:
        db.delete(user_settings)
        db.commit()
    
    # Create new default settings
    default_settings = UserSettings(user_id=current_user.id, allowed_subnet=app_settings.SCOPE_SUBNET)
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


@router.post("/settings/integrations/n8n/test")
async def test_n8n_webhook(
    current_user: User = Depends(get_current_user),
):
    """Send a test webhook event to n8n to validate the integration."""

    webhook_url = app_settings.N8N_WEBHOOK_URL_CLEAN
    if not webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="N8N_WEBHOOK_URL is not configured",
        )

    payload = {
        "event": "n8n_test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "source": "trinity_backend",
        "user": {"id": current_user.id, "email": current_user.email},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            ok = 200 <= response.status_code < 300
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to reach n8n webhook: {exc}",
        )

    if not ok:
        detail = f"n8n webhook returned HTTP {response.status_code}"
        try:
            body = response.json()
            msg = body.get("message")
            hint = body.get("hint")
            if msg:
                detail += f": {msg}"
            if hint:
                detail += f" (hint: {hint})"
        except Exception:
            text = (response.text or "").strip()
            if text:
                detail += f": {text[:300]}"

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        )

    return {"message": "n8n webhook test sent", "payload": payload}
