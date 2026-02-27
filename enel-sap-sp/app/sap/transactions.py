"""SAP transaction runners for ZUCRM_039 and IW59."""
from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from datetime import date
from pathlib import Path

from app.core.settings import Settings
from app.sap.clipboard import WindowsClipboardService
from app.sap.exceptions import SapAutomationError, SapExportTimeoutError
from app.sap.file_watcher import ExportFileWatcher
from app.sap.gui_client import SapSessionFacade


logger = logging.getLogger(__name__)


class SapExportDialogService:
    """Handles SAP export popups and enforces output path."""

    def __init__(self, export_dir: Path):
        self._export_dir = export_dir
        self._export_dir.mkdir(parents=True, exist_ok=True)

    def finalize_export(self, session: SapSessionFacade) -> float:
        """Sets DY_PATH when available and confirms export."""
        export_path = self._to_sap_path(self._export_dir)
        path_field = "wnd[1]/usr/ctxtDY_PATH"
        save_button = "wnd[1]/tbar[0]/btn[11]"
        ok_button = "wnd[1]/tbar[0]/btn[0]"
        overwrite_yes = "wnd[1]/usr/btnSPOP-OPTION1"

        # Some SAP layouts show an intermediate confirmation before path/filename fields.
        if session.exists(ok_button) and not session.exists(path_field):
            session.press(ok_button)
            time.sleep(0.2)

        if session.exists(path_field):
            session.set_text(path_field, export_path)
            logger.info("Diretorio de exportacao SAP definido: %s", export_path)

        started_epoch = time.time()
        if session.exists(save_button):
            session.press(save_button)
        elif session.exists(ok_button):
            session.press(ok_button)
        else:
            raise SapAutomationError("Dialogo de exportacao SAP nao encontrado para confirmar salvamento.")

        if session.exists(overwrite_yes):
            session.press(overwrite_yes)

        return started_epoch

    @staticmethod
    def _to_sap_path(path: Path) -> str:
        return str(path).replace("/", "\\")


class Zucrm039TransactionRunner:
    """Executes ZUCRM_039 and captures exported file path."""

    def __init__(self, settings: Settings, file_watcher: ExportFileWatcher):
        self._settings = settings
        self._file_watcher = file_watcher
        self._export_dialog = SapExportDialogService(settings.sap_zucrm_export_dir)

    @staticmethod
    def _format_sap_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")

    def run(self, session: SapSessionFacade, start_date: date, end_date: date) -> Path:
        logger.info("Executando transacao %s", self._settings.sap_transaction_zucrm)
        baseline = self._file_watcher.snapshot()
        baseline_all = self._snapshot_all_excel_files()

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
        # executar relatorio -> menu exportar -> confirmar popup + salvar no diretorio da ZUCRM.
        session.press("wnd[0]/tbar[1]/btn[8]")
        session.select("wnd[0]/mbar/menu[0]/menu[4]/menu[1]")
        started_epoch = self._export_dialog.finalize_export(session)

        try:
            exported_file = self._file_watcher.wait_for_export(
                baseline=baseline,
                execution_started_epoch=started_epoch,
            )
        except SapExportTimeoutError:
            fallback_file = self._find_export_named_fallback(
                baseline_all=baseline_all,
                execution_started_epoch=started_epoch,
            )
            if fallback_file is None:
                raise
            logger.warning(
                "Arquivo ZUCRM nao detectado pelo glob configurado; usando fallback por nome: %s",
                fallback_file,
            )
            exported_file = fallback_file

        logger.info("Arquivo ZUCRM detectado: %s", exported_file)
        return exported_file

    def _snapshot_all_excel_files(self) -> dict[Path, float]:
        snapshot: dict[Path, float] = {}
        directory = self._settings.sap_zucrm_export_dir
        for pattern in ("*.XLSX", "*.xlsx"):
            for path in directory.glob(pattern):
                try:
                    resolved = path.resolve()
                    snapshot[resolved] = resolved.stat().st_mtime
                except OSError:
                    continue
        return snapshot

    def _find_export_named_fallback(self, baseline_all: dict[Path, float], execution_started_epoch: float) -> Path | None:
        directory = self._settings.sap_zucrm_export_dir
        candidate: Path | None = None
        candidate_mtime = -1.0

        for pattern in ("export*.XLSX", "export*.xlsx"):
            for path in directory.glob(pattern):
                try:
                    resolved = path.resolve()
                    mtime = resolved.stat().st_mtime
                except OSError:
                    continue

                previous_mtime = baseline_all.get(resolved)
                is_new = previous_mtime is None
                is_updated = previous_mtime is not None and mtime > previous_mtime + 1e-6
                is_after_execution = mtime >= execution_started_epoch - 1.0

                if (is_new or is_updated) and is_after_execution and mtime > candidate_mtime:
                    candidate = resolved
                    candidate_mtime = mtime

        return candidate


class SapNavigationService:
    """Navigation helpers inside SAP session."""

    def __init__(self, max_f3_presses: int):
        self._max_f3_presses = max_f3_presses

    def back_until_transaction_screen(self, session: SapSessionFacade) -> None:
        """Press F3 repeatedly (at least 3x) before moving to IW59."""
        target_field = "wnd[0]/tbar[0]/okcd"
        back_button = "wnd[0]/tbar[0]/btn[3]"
        min_presses = 3
        max_presses = max(min_presses, min(self._max_f3_presses, 4))
        pressed = 0

        for _ in range(max_presses):
            if not session.exists(back_button):
                logger.info("Botao F3 indisponivel; seguindo fluxo para proxima transacao.")
                return

            session.press(back_button)
            pressed += 1
            time.sleep(0.3)

            # Garante pelo menos 3 pressionamentos, podendo parar no 4o
            # quando o campo de comando estiver disponivel.
            if pressed >= min_presses and session.exists(target_field):
                logger.info("Retorno via F3 concluido com %d pressionamento(s).", pressed)
                return

        logger.info("Retorno via F3 executado com %d pressionamento(s).", pressed)


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
        self._export_dialog = SapExportDialogService(settings.sap_iw59_export_dir)

    def run(self, session: SapSessionFacade, notes: list[str]) -> Path | None:
        logger.info("Executando transacao %s com %d nota(s)", self._settings.sap_transaction_iw59, len(notes))

        baseline = self._file_watcher.snapshot()

        session.maximize()
        session.set_text("wnd[0]/tbar[0]/okcd", self._settings.sap_transaction_iw59)
        session.send_vkey(0)

        multi_select_btn = "wnd[0]/usr/btn%_QMNUM_%_APP_%-VALU_PUSH"
        self._wait_for_control(session, multi_select_btn, timeout_seconds=8.0)
        session.press(multi_select_btn)

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

        export_started = self._export_dialog.finalize_export(session)

        try:
            exported_file = self._file_watcher.wait_for_export(
                baseline=baseline,
                execution_started_epoch=export_started,
            )
            copied_file = self._copy_to_new_workbook(exported_file)
            logger.info("Arquivo IW59 detectado: %s | copia completa criada: %s", exported_file, copied_file)
            return copied_file
        except SapExportTimeoutError:
            logger.warning(
                "Fluxo IW59 executado, mas nenhum arquivo novo foi detectado no diretorio monitorado."
            )
            return None

    @staticmethod
    def _wait_for_control(session: SapSessionFacade, control_id: str, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if session.exists(control_id):
                return
            time.sleep(0.3)
        raise SapAutomationError(f"Elemento SAP nao encontrado: {control_id}")

    def _copy_to_new_workbook(self, source_file: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = source_file.suffix or ".xlsx"
        target_file = self._settings.sap_iw59_export_dir / f"iw59_copia_completa_{timestamp}{suffix}"
        shutil.copy2(source_file, target_file)
        return target_file
