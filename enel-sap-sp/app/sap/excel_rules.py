"""Business rules over ZUCRM export file."""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

import pandas as pd

from app.sap.exceptions import SapAutomationError


logger = logging.getLogger(__name__)


class ExcelNoteRuleService:
    """Extracts normalized note values for IW59 input."""

    _TARGET_COLUMN_NORMALIZED = {"nnotamedida", "nonotamedida"}

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        no_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return "".join(ch.lower() for ch in no_accents if ch.isalnum())

    def _resolve_note_column(self, columns: list[str]) -> str:
        for column in columns:
            if self._normalize(str(column)) in self._TARGET_COLUMN_NORMALIZED:
                return column
        raise SapAutomationError("Coluna 'Nº Nota/Medida' nao encontrada no arquivo exportado da ZUCRM.")

    def extract_notes_for_iw59(self, excel_path: Path) -> list[str]:
        if not excel_path.exists():
            raise SapAutomationError(f"Arquivo da ZUCRM nao encontrado: {excel_path}")

        try:
            df = pd.read_excel(excel_path, dtype=str, engine="openpyxl")
        except Exception as exc:
            raise SapAutomationError(f"Falha ao ler arquivo exportado: {excel_path}") from exc

        if df.empty:
            raise SapAutomationError("Arquivo exportado da ZUCRM veio vazio.")

        note_column = self._resolve_note_column(df.columns.tolist())

        raw_values = df[note_column].astype(str).str.strip()
        filtered = raw_values[~raw_values.str.contains("/000", na=False)]

        numeric = pd.to_numeric(
            filtered.str.replace(r"\D", "", regex=True),
            errors="coerce",
        )

        notes = [str(int(value)) for value in numeric.dropna().tolist()]
        unique_notes = list(dict.fromkeys(notes))

        logger.info(
            "Notas extraidas da ZUCRM: total=%d | validas_sem_/000=%d | unicas=%d",
            len(raw_values),
            len(notes),
            len(unique_notes),
        )

        if not unique_notes:
            raise SapAutomationError("Nenhuma nota valida encontrada para enviar a IW59.")

        return unique_notes
