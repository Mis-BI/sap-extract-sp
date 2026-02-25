"""Domain models for SAP automation flow."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SapRunCommand:
    """Input command to execute SAP flow."""

    start_date: date
    end_date: date


@dataclass(frozen=True)
class SapRunResult:
    """Output of SAP flow execution."""

    zucrm_export_file: str
    iw59_export_file: str | None
    notes_count: int
