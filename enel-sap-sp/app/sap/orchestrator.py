"""Coordinates SAP automation flow end-to-end."""
from __future__ import annotations

import logging

from app.core.settings import Settings
from app.sap.excel_rules import ExcelNoteRuleService
from app.sap.gui_client import SapGuiClient
from app.sap.models import SapRunCommand, SapRunResult
from app.sap.transactions import Iw59TransactionRunner, SapNavigationService, Zucrm039TransactionRunner


logger = logging.getLogger(__name__)


class SapAutomationOrchestrator:
    """Runs login, ZUCRM extraction, note processing and IW59 execution."""

    def __init__(
        self,
        settings: Settings,
        sap_client: SapGuiClient,
        zucrm_runner: Zucrm039TransactionRunner,
        iw59_runner: Iw59TransactionRunner,
        note_rules: ExcelNoteRuleService,
        navigator: SapNavigationService,
    ):
        self._settings = settings
        self._sap_client = sap_client
        self._zucrm_runner = zucrm_runner
        self._iw59_runner = iw59_runner
        self._note_rules = note_rules
        self._navigator = navigator

    def run(self, command: SapRunCommand) -> SapRunResult:
        if command.end_date < command.start_date:
            raise ValueError("end_date deve ser maior ou igual a start_date")

        self._settings.validate_sap_credentials()

        logger.info(
            "Inicio da automacao SAP | periodo=%s ate %s",
            command.start_date.isoformat(),
            command.end_date.isoformat(),
        )

        session = self._sap_client.connect_and_login()

        zucrm_file = self._zucrm_runner.run(
            session=session,
            start_date=command.start_date,
            end_date=command.end_date,
        )

        notes = self._note_rules.extract_notes_for_iw59(zucrm_file)

        self._navigator.back_until_transaction_screen(session)

        iw59_file = self._iw59_runner.run(session=session, notes=notes)

        logger.info(
            "Automacao concluida | arquivo_zucrm=%s | arquivo_iw59=%s | notas=%d",
            zucrm_file,
            iw59_file,
            len(notes),
        )

        return SapRunResult(
            zucrm_export_file=str(zucrm_file),
            iw59_export_file=str(iw59_file) if iw59_file else None,
            notes_count=len(notes),
        )
