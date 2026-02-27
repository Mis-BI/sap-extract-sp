"""Dependency graph for SAP automation route."""
from __future__ import annotations

from fastapi import Depends

from app.core.settings import Settings, get_settings
from app.sap.clipboard import WindowsClipboardService
from app.sap.excel_rules import ExcelNoteRuleService
from app.sap.file_watcher import ExportFileWatcher
from app.sap.gui_client import SapGuiClient
from app.sap.orchestrator import SapAutomationOrchestrator
from app.sap.transactions import Iw59TransactionRunner, SapNavigationService, Zucrm039TransactionRunner


def get_orchestrator(settings: Settings = Depends(get_settings)) -> SapAutomationOrchestrator:
    """Builds orchestrator with concrete infrastructure services."""
    zucrm_watcher = ExportFileWatcher(
        directory=settings.sap_zucrm_export_dir,
        file_glob=settings.sap_zucrm_export_glob,
        timeout_seconds=settings.sap_export_timeout_seconds,
    )
    iw59_watcher = ExportFileWatcher(
        directory=settings.sap_iw59_export_dir,
        file_glob=settings.sap_iw59_export_glob,
        timeout_seconds=settings.sap_export_timeout_seconds,
    )

    return SapAutomationOrchestrator(
        settings=settings,
        sap_client=SapGuiClient(settings=settings),
        zucrm_runner=Zucrm039TransactionRunner(settings=settings, file_watcher=zucrm_watcher),
        iw59_runner=Iw59TransactionRunner(
            settings=settings,
            file_watcher=iw59_watcher,
            clipboard_service=WindowsClipboardService(),
        ),
        note_rules=ExcelNoteRuleService(),
        navigator=SapNavigationService(max_f3_presses=settings.sap_f3_max_presses),
    )
