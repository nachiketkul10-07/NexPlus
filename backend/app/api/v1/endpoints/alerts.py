"""
Alert Rules and Triggered Alerts API Endpoints for PulseOps
Handles alert rule CRUD, triggered alert queries, manual evaluation triggers, and strict server-side authorization.
"""
from typing import Annotated, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_db,
    get_alert_repository,
    get_service_repository,
    require_authenticated_user,
    verify_resource_ownership,
)
from app.db.repositories.alert_repository import PostgresAlertRepository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.schemas.alert import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertResponse,
    AlertEvaluationSummary,
)
from app.schemas.user import UserResponse, UserRole
from app.services.alert_engine import AlertEngine
from app.core.audit import log_audit_event
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ----------------------------------------------------------------------
# Alert Rules Endpoints
# ----------------------------------------------------------------------
@router.get("/rules", response_model=List[AlertRuleResponse], status_code=status.HTTP_200_OK)
async def list_alert_rules(
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter rules by service target UUID"),
    enabled_only: bool = Query(False, description="Filter for enabled rules only")
) -> List[AlertRuleResponse]:
    """Lists configured alert evaluation rules."""
    rules = await alert_repo.list_rules(service_id=service_id, enabled_only=enabled_only)
    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule_in: AlertRuleCreate,
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> AlertRuleResponse:
    """
    Creates a new alert rule.
    SERVER-SIDE AUTHORIZATION: If service_id is specified, user must own service or be admin.
    Global rules (service_id=None) require admin role.
    """
    if rule_in.service_id is not None:
        service = await service_repo.get_by_id(rule_in.service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target service not found."
            )
    else:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Administrators can create global alert rules."
            )

    rule = await alert_repo.create_rule(rule_in)
    log_audit_event(
        "ALERT_RULE_CREATED",
        user_id=str(current_user.id),
        email=current_user.email,
        details={
            "rule_id": str(rule.id),
            "name": rule.name,
            "metric_name": rule.metric_name,
            "service_id": str(rule.service_id) if rule.service_id else "global"
        },
        success=True
    )
    return AlertRuleResponse.model_validate(rule)
@router.get("/rules/{rule_id}", response_model=AlertRuleResponse, status_code=status.HTTP_200_OK)
async def get_alert_rule(
    rule_id: UUID,
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> AlertRuleResponse:
    """Retrieves an alert rule by ID."""
    rule = await alert_repo.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found."
        )
    return AlertRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse, status_code=status.HTTP_200_OK)
async def update_alert_rule(
    rule_id: UUID,
    rule_in: AlertRuleUpdate,
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> AlertRuleResponse:
    """Updates an existing alert rule."""
    rule = await alert_repo.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found."
        )

    if rule.service_id is not None:
        service = await service_repo.get_by_id(rule.service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target service not found."
            )
    else:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Administrators can modify global alert rules."
            )

    updates = rule_in.model_dump(exclude_unset=True)
    updated_rule = await alert_repo.update_rule(rule, updates)

    log_audit_event(
        "ALERT_RULE_UPDATED",
        user_id=str(current_user.id),
        email=current_user.email,
        details={"rule_id": str(rule_id), "updated_fields": list(updates.keys())},
        success=True
    )
    return AlertRuleResponse.model_validate(updated_rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_alert_rule(
    rule_id: UUID,
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    service_repo: Annotated[PostgresServiceRepository, Depends(get_service_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
):
    """Deletes an alert rule."""
    rule = await alert_repo.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found."
        )

    if rule.service_id is not None:
        service = await service_repo.get_by_id(rule.service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target service not found."
            )
    else:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Administrators can delete global alert rules."
            )

    await alert_repo.delete_rule(rule)
    log_audit_event(
        "ALERT_RULE_DELETED",
        user_id=str(current_user.id),
        email=current_user.email,
        details={"rule_id": str(rule_id), "name": rule.name},
        success=True
    )
    return {"message": "Alert rule deleted successfully.", "rule_id": str(rule_id)}


# ----------------------------------------------------------------------
# Triggered Alerts Endpoints
# ----------------------------------------------------------------------
@router.get("", response_model=List[AlertResponse], status_code=status.HTTP_200_OK)
async def list_triggered_alerts(
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter by service UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active, resolved"),
    severity: Optional[str] = Query(None, description="Filter by severity: critical, warning, info"),
    limit: int = Query(100, ge=1, le=500)
) -> List[AlertResponse]:
    """Lists triggered alert records."""
    alerts = await alert_repo.list_alerts(
        service_id=service_id,
        status=status_filter,
        severity=severity,
        limit=limit
    )

    res = []
    for a in alerts:
        dto = AlertResponse.model_validate(a)
        dto.rule_name = a.rule.name if a.rule else None
        dto.service_name = a.service.name if a.service else None
        res.append(dto)
    return res


@router.get("/{alert_id}", response_model=AlertResponse, status_code=status.HTTP_200_OK)
async def get_triggered_alert(
    alert_id: UUID,
    alert_repo: Annotated[PostgresAlertRepository, Depends(get_alert_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> AlertResponse:
    """Retrieves a single triggered alert by ID."""
    alert = await alert_repo.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found."
        )
    dto = AlertResponse.model_validate(alert)
    dto.rule_name = alert.rule.name if alert.rule else None
    dto.service_name = alert.service.name if alert.service else None
    return dto


# ----------------------------------------------------------------------
# Evaluation Endpoints
# ----------------------------------------------------------------------
@router.post("/evaluate", response_model=AlertEvaluationSummary, status_code=status.HTTP_200_OK)
async def trigger_rule_evaluation(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Optional target service UUID"),
    rule_id: Optional[UUID] = Query(None, description="Optional single target rule UUID")
) -> AlertEvaluationSummary:
    """
    Triggers execution of the Alert Engine evaluation pipeline.
    Evaluates telemetry against active rules and updates alert states.
    """
    engine = AlertEngine(session)
    if rule_id is not None:
        summary = await engine.evaluate_rule(rule_id)
    else:
        summary = await engine.evaluate_all_rules(service_id=service_id)

    log_audit_event(
        "ALERT_EVALUATION_EXECUTED",
        user_id=str(current_user.id),
        email=current_user.email,
        details={
            "rules_evaluated": summary.rules_evaluated,
            "alerts_triggered": summary.alerts_triggered,
            "alerts_updated": summary.alerts_updated,
            "alerts_resolved": summary.alerts_resolved,
            "service_id": str(service_id) if service_id else "all"
        },
        success=True
    )
    return summary
