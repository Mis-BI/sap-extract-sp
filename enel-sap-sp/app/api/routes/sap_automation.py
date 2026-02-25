"""HTTP route to execute SAP automation flow."""
from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from app.sap.dependencies import get_orchestrator
from app.sap.exceptions import SapAutomationError
from app.sap.models import SapRunCommand
from app.sap.orchestrator import SapAutomationOrchestrator


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["sap-automation"])


class SapAutomationRequest(BaseModel):
    """Request payload for SAP run."""

    start_date: date = Field(
        ...,
        description="Data inicial (YYYY-MM-DD, DD.MM.YYYY ou DD/MM/YYYY)",
        validation_alias=AliasChoices("start_date", "startDate"),
    )
    end_date: date = Field(
        ...,
        description="Data final (YYYY-MM-DD, DD.MM.YYYY ou DD/MM/YYYY)",
        validation_alias=AliasChoices("end_date", "endDate"),
    )

    @staticmethod
    def _parse_flexible_date(value: object) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            normalized = value.strip()
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(normalized, fmt).date()
                except ValueError:
                    continue
        raise ValueError("Formato de data invalido. Use YYYY-MM-DD, DD.MM.YYYY ou DD/MM/YYYY")

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, value: object) -> date:
        return cls._parse_flexible_date(value)

    @model_validator(mode="after")
    def validate_period(self) -> "SapAutomationRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date deve ser maior ou igual a start_date")
        return self


class SapAutomationResponse(BaseModel):
    """Result payload for SAP run."""

    status: str
    zucrm_export_file: str
    iw59_export_file: str | None
    notes_count: int


@router.post("/sap/run", response_model=SapAutomationResponse)
def run_sap_automation(
    payload: SapAutomationRequest,
    orchestrator: SapAutomationOrchestrator = Depends(get_orchestrator),
) -> SapAutomationResponse:
    """Runs the end-to-end SAP automation process."""
    logger.info(
        "Requisicao de automacao recebida | start=%s | end=%s",
        payload.start_date.isoformat(),
        payload.end_date.isoformat(),
    )

    command = SapRunCommand(start_date=payload.start_date, end_date=payload.end_date)

    try:
        result = orchestrator.run(command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SapAutomationError as exc:
        logger.exception("Falha na automacao SAP: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Erro inesperado na automacao SAP: %s", exc)
        raise HTTPException(status_code=500, detail="Erro inesperado na automacao SAP") from exc

    return SapAutomationResponse(
        status="success",
        zucrm_export_file=result.zucrm_export_file,
        iw59_export_file=result.iw59_export_file,
        notes_count=result.notes_count,
    )
