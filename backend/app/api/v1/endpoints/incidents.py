"""
Incidents API Endpoints for PulseOps
Provides incident lifecycle management, state machine updates, responder assignment, and timeline logging.
"""
from typing import Annotated, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.deps import (
    get_db,
    get_incident_repository,
    get_service_repository,
    require_authenticated_user,
    verify_resource_ownership,
)
from app.db.repositories.incident_repository import PostgresIncidentRepository
from app.db.repositories.service_repository import PostgresServiceRepository
from app.schemas.incident import (
    IncidentResponse,
    IncidentUpdate,
    IncidentEventResponse,
    IncidentEventCreate,
)
from app.schemas.user import UserResponse
from app.services.incident_service import IncidentService
from app.schemas.ai import AIAnalysisResponse, AIAnalysisRequest
from app.services.ai.ai_service import AIService

router = APIRouter()


def _build_incident_response(incident) -> IncidentResponse:
    """Helper to convert Incident ORM model to IncidentResponse DTO with display fields."""
    dto = IncidentResponse.model_validate(incident)
    if incident.service:
        dto.service_name = incident.service.name
    if incident.assignee:
        dto.assignee_email = incident.assignee.email
        dto.assignee_name = incident.assignee.full_name
    if incident.originating_alert:
        if incident.originating_alert.rule:
            dto.originating_alert_rule_name = incident.originating_alert.rule.name
        dto.evidence = incident.originating_alert.evidence
    return dto


@router.get("", response_model=List[IncidentResponse], status_code=status.HTTP_200_OK)
async def list_incidents(
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    service_id: Optional[UUID] = Query(None, description="Filter by target service UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: open, investigating, resolved"),
    severity: Optional[str] = Query(None, description="Filter by severity: critical, warning, info"),
    assignee_user_id: Optional[UUID] = Query(None, description="Filter by assigned user UUID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> List[IncidentResponse]:
    """Lists recent operational incidents with pagination and filtering."""
    incidents = await incident_repo.list_incidents(
        service_id=service_id,
        status=status_filter,
        severity=severity,
        assignee_user_id=assignee_user_id,
        limit=limit,
        offset=offset
    )
    return [_build_incident_response(inc) for inc in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse, status_code=status.HTTP_200_OK)
async def get_incident(
    incident_id: UUID,
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> IncidentResponse:
    """Retrieves a single incident by ID."""
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    return _build_incident_response(incident)


@router.patch("/{incident_id}", response_model=IncidentResponse, status_code=status.HTTP_200_OK)
async def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> IncidentResponse:
    """
    Updates incident status, assignee, or resolution note.
    Enforces server-side authorization and state machine transition rules.
    """
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    inc_service = IncidentService(session)

    try:
        if "assignee_user_id" in payload.model_fields_set:
            incident = await inc_service.assign_incident(
                incident=incident,
                assignee_user_id=payload.assignee_user_id,
                actor_user_id=current_user.id,
                actor_email=current_user.email
            )

        if payload.status:
            incident = await inc_service.transition_incident_status(
                incident=incident,
                target_status=payload.status,
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                resolution_note=payload.resolution_note
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    refreshed = await incident_repo.get_incident_by_id(incident_id)
    return _build_incident_response(refreshed)


@router.get("/{incident_id}/events", response_model=List[IncidentEventResponse], status_code=status.HTTP_200_OK)
async def list_incident_events(
    incident_id: UUID,
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> List[IncidentEventResponse]:
    """Retrieves append-only timeline events for an incident in chronological order."""
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    events = await incident_repo.get_timeline_events(incident_id)
    res = []
    for ev in events:
        dto = IncidentEventResponse.model_validate(ev)
        dto.actor_name = ev.actor.full_name if ev.actor else ("System" if ev.actor_user_id is None else None)
        res.append(dto)
    return res


@router.post("/{incident_id}/events", response_model=IncidentEventResponse, status_code=status.HTTP_201_CREATED)
async def add_incident_event(
    incident_id: UUID,
    payload: IncidentEventCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> IncidentEventResponse:
    """Appends an investigation note or timeline event to an incident."""
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    inc_service = IncidentService(session)
    event = await inc_service.add_incident_note(
        incident=incident,
        message=payload.message,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        metadata=payload.metadata_json
    )

    dto = IncidentEventResponse.model_validate(event)
    dto.actor_name = current_user.full_name
    return dto



def _build_ai_analysis_response(record) -> AIAnalysisResponse:
    """Helper to convert AIAnalysis ORM model to AIAnalysisResponse DTO."""
    snapshot = record.evidence_snapshot or {}
    evidence_raw = snapshot.get("evidence", [])
    next_checks_raw = snapshot.get("next_checks", [])
    status_str = snapshot.get("status", "generated")

    # Format evidence items
    evidence = [
        {
            "source_type": item.get("source_type", "telemetry"),
            "source_reference": item.get("source_reference"),
            "observation": item.get("observation", "")
        }
        for item in evidence_raw
    ]

    # Format possible causes
    possible_causes = []
    if record.possible_factors:
        for factor in record.possible_factors:
            if isinstance(factor, str):
                possible_causes.append({
                    "statement": factor,
                    "supporting_evidence": [],
                    "confidence": "medium"
                })

    return AIAnalysisResponse(
        id=record.id,
        incident_id=record.incident_id,
        provider=settings.AI_PROVIDER,
        model_name=record.model_name,
        prompt_version=record.prompt_version,
        status=status_str,
        summary=record.summary,
        evidence=evidence,
        possible_causes=possible_causes,
        next_checks=next_checks_raw,
        limitations_note=record.limitations_note,
        created_at=record.created_at
    )


@router.post("/{incident_id}/ai-analysis", response_model=AIAnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze_incident(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)],
    payload: Optional[AIAnalysisRequest] = None
) -> AIAnalysisResponse:
    """
    Generates or refreshes advisory AI analysis for an incident.
    Constructs sanitized context, evaluates telemetry evidence, and returns structured analysis.
    """
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    ai_service = AIService(session)
    force_refresh = payload.force_refresh if payload else False
    record = await ai_service.analyze_incident(incident, force_refresh=force_refresh)

    return _build_ai_analysis_response(record)


@router.get("/{incident_id}/ai-analysis", response_model=AIAnalysisResponse, status_code=status.HTTP_200_OK)
async def get_latest_ai_analysis(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    incident_repo: Annotated[PostgresIncidentRepository, Depends(get_incident_repository)],
    current_user: Annotated[UserResponse, Depends(require_authenticated_user)]
) -> AIAnalysisResponse:
    """Retrieves latest generated AI analysis snapshot for an incident."""
    incident = await incident_repo.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found."
        )

    ai_service = AIService(session)
    record = await ai_service.get_latest_analysis(incident_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No AI analysis has been generated for this incident yet."
        )

    return _build_ai_analysis_response(record)
