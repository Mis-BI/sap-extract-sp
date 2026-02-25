"""SAP transaction runners for ZUCRM_039 and IW59."""
from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

from app.core.settings import Settings
from app.sap.clipboard import WindowsClipboardService
from app.sap.exceptions import SapExportTimeoutError
from app.sap.file_watcher import ExportFileWatcher
from app.sap.gui_client import SapSessionFacade


logger = logging.getLogger(__name__)


class Zucrm039TransactionRunner:
    """Executes ZUCRM_039 and captures exported file path."""

    def __init__(self, settings: Settings, file_watcher: ExportFileWatcher):
        self._settings = settings
        self._file_watcher = file_watcher

    @staticmethod
    def _format_sap_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")

    def run(self, session: SapSessionFacade, start_date: date, end_date: date) -> Path:
        logger.info("Executando transacao %s", self._settings.sap_transaction_zucrm)
        baseline = self._file_watcher.snapshot()

        session.maximize()
        session.set_text("wnd[0]/tbar[0]/okcd", self._settings.sap_transaction_zucrm)
        session.send_vkey(0)

        session.set_text("wnd[0]/usr/ctxtPC_QMART", self._settings.sap_qmart)
        session.set_text("wnd[0]/usr/ctxtSD_QMDAT-LOW", self._format_sap_date(start_date))
        session.set_text("wnd[0]/usr/ctxtSD_QMDAT-HIGH", self._format_sap_date(end_date))
        session.set_text("wnd[0]/usr/ctxtSC_QMCOD-LOW", "*")
        session.set_text("wnd[0]/usr/ctxtPC_VARIA", self._settings.sap_variation)
        session.set_focus("wnd[0]/usr/ctxtPC_VARIA")
        caret_pos = 9 if len(self._settings.sap_variation) >= 9 else len(self._settings.sap_variation)
        session.set_caret_position("wnd[0]/usr/ctxtPC_VARIA", caret_pos)

        # Fluxo alinhado ao script informado:
        # executar relatorio -> menu exportar -> confirmar popup.
        session.press("wnd[0]/tbar[1]/btn[8]")
        started_epoch = time.time()
        session.select("wnd[0]/mbar/menu[0]/menu[4]/menu[1]")
        session.press("wnd[1]/tbar[0]/btn[0]")

        exported_file = self._file_watcher.wait_for_export(
            baseline=baseline,
            execution_started_epoch=started_epoch,
        )

        logger.info("Arquivo ZUCRM detectado: %s", exported_file)
        return exported_file


class SapNavigationService:
    """Navigation helpers inside SAP session."""

    def __init__(self, max_f3_presses: int):
        self._max_f3_presses = max_f3_presses

    def back_until_transaction_screen(self, session: SapSessionFacade) -> None:
        """Press F3 repeatedly until selection field appears or max attempts reached."""
        target_field = "wnd[0]/usr/ctxtPC_QMART"
        back_button = "wnd[0]/tbar[0]/btn[3]"

        for attempt in range(self._max_f3_presses):
            if session.exists(target_field):
                logger.info("Retorno via F3 concluido apos %d tentativa(s).", attempt)
                return

            if not session.exists(back_button):
                logger.info("Botao F3 indisponivel; seguindo fluxo para proxima transacao.")
                return

            session.press(back_button)
            time.sleep(0.3)

        logger.warning(
            "Limite de F3 atingido (%d). Seguindo para IW59 mesmo sem confirmar tela de transacao.",
            self._max_f3_presses,
        )


class Iw59TransactionRunner:
    """Executes IW59 and feeds notes from clipboard."""

    def __init__(
        self,
        settings: Settings,
        file_watcher: ExportFileWatcher,
        clipboard_service: WindowsClipboardService,
    ):
        self._settings = settings
        self._file_watcher = file_watcher
        self._clipboard_service = clipboard_service

    def run(self, session: SapSessionFacade, notes: list[str]) -> Path | None:
        logger.info("Executando transacao %s com %d nota(s)", self._settings.sap_transaction_iw59, len(notes))

        baseline = self._file_watcher.snapshot()

        session.maximize()
        session.set_text("wnd[0]/tbar[0]/okcd", self._settings.sap_transaction_iw59)
        session.send_vkey(0)

        session.press("wnd[0]/usr/btn%_QMNUM_%_APP_%-VALU_PUSH")

        self._clipboard_service.copy_lines(notes)
        session.press("wnd[1]/tbar[0]/btn[24]")
        session.press("wnd[1]/tbar[0]/btn[8]")

        session.press("wnd[0]/tbar[1]/btn[8]")
        session.select("wnd[0]/mbar/menu[0]/menu[6]")
        session.press("wnd[1]/tbar[0]/btn[0]")

        option_id = (
            "wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/"
            "sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[0,0]"
        )
        session.select(option_id)
        session.set_focus(option_id)
        session.press("wnd[1]/tbar[0]/btn[0]")

        export_started = time.time()
        session.press("wnd[1]/tbar[0]/btn[0]")

        try:
            exported_file = self._file_watcher.wait_for_export(
                baseline=baseline,
                execution_started_epoch=export_started,
            )
            logger.info("Arquivo IW59 detectado: %s", exported_file)
            return exported_file
        except SapExportTimeoutError:
            logger.warning(
                "Fluxo IW59 executado, mas nenhum arquivo novo foi detectado no diretorio monitorado."
            )
            return None
