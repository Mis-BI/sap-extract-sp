"""UI automation fallback for SAP Logon selection screen."""
from __future__ import annotations

import logging
import re
import time
import unicodedata

from app.sap.exceptions import SapAutomationError


logger = logging.getLogger(__name__)


class SapLogonUiAutomation:
    """Selects server and connection directly in SAP Logon window."""

    def __init__(self, timeout_seconds: int = 30):
        self._timeout_seconds = timeout_seconds

    def open_connection(self, server_name: str, connection_name: str) -> None:
        """Clicks server on left tree and double-clicks target connection on right list."""
        Application = self._import_pywinauto_application()
        window = self._connect_sap_logon_window(Application)

        try:
            window.set_focus()
        except Exception:
            pass

        self._select_server(window, server_name)
        self._double_click_connection(window, connection_name)

    @staticmethod
    def _import_pywinauto_application():
        try:
            from pywinauto.application import Application  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on runtime env
            raise SapAutomationError(
                "Fallback de UI do SAP Logon requer pywinauto. Instale: pip install pywinauto"
            ) from exc
        return Application

    def _connect_sap_logon_window(self, Application):
        deadline = time.monotonic() + self._timeout_seconds
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            try:
                app = Application(backend="uia").connect(title_re=r"SAP Logon.*")
                window = app.window(title_re=r"SAP Logon.*")
                if window.exists(timeout=1):
                    return window
            except Exception as exc:
                last_error = exc
            time.sleep(0.5)

        raise SapAutomationError("Janela 'SAP Logon' nao encontrada para automacao de clique.") from last_error

    def _select_server(self, window, server_name: str) -> None:
        target = self._normalize(server_name)
        if not target:
            return

        tree_items = window.descendants(control_type="TreeItem")
        candidate = self._best_control_match(tree_items, target)
        if candidate is None:
            logger.warning("Server '%s' nao encontrado na arvore do SAP Logon; seguindo tentativa de conexao.", server_name)
            return

        logger.info("Selecionando server no SAP Logon: %s", candidate.window_text())
        candidate.click_input()
        time.sleep(0.3)

    def _double_click_connection(self, window, connection_name: str) -> None:
        target = self._normalize(connection_name.replace("...", " "))
        if not target:
            raise SapAutomationError("SAP_CONNECTION_NAME vazio no .env")

        rows = self._collect_connection_rows(window)
        if not rows:
            raise SapAutomationError("Nenhuma conexao visivel encontrada na grade do SAP Logon.")

        best_row, best_score = self._best_row_match(rows, target)
        if best_row is None or best_score <= 0:
            available = ", ".join(text for text, _ in rows[:10])
            raise SapAutomationError(
                "Conexao SAP nao encontrada na grade do Logon. "
                f"Filtro: '{connection_name}'. Primeiras conexoes visiveis: {available}"
            )

        logger.info("Abrindo conexao SAP por clique: %s", best_row.window_text())
        best_row.double_click_input()

    @staticmethod
    def _collect_connection_rows(window):
        controls = []
        seen = set()
        for control_type in ("DataItem", "ListItem"):
            for control in window.descendants(control_type=control_type):
                text = control.window_text().strip()
                if not text:
                    continue
                if text in seen:
                    continue
                seen.add(text)
                controls.append((text, control))
        return controls

    def _best_row_match(self, rows, target: str):
        best_row = None
        best_score = -1
        for text, control in rows:
            score = self._match_score(text, target)
            if score > best_score:
                best_score = score
                best_row = control
        return best_row, best_score

    def _best_control_match(self, controls, target: str):
        best = None
        best_score = -1
        for control in controls:
            text = control.window_text().strip()
            score = self._match_score(text, target)
            if score > best_score:
                best_score = score
                best = control
        if best_score <= 0:
            return None
        return best

    def _match_score(self, text: str, target: str) -> int:
        if not text:
            return -1

        normalized_text = self._normalize(text)
        if not normalized_text:
            return -1

        if normalized_text == target:
            return 100

        if target in normalized_text:
            return 90

        if normalized_text in target and len(normalized_text) >= 6:
            return 70

        score = 0
        target_tokens = [token for token in re.split(r"\s+", target) if token]
        text_tokens = set(token for token in re.split(r"\s+", normalized_text) if token)

        for token in target_tokens:
            if len(token) <= 1:
                continue
            if token in text_tokens:
                score += 8
            elif token in normalized_text:
                score += 5

        if target_tokens and normalized_text.startswith(target_tokens[0]):
            score += 10

        return score

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(text))
        without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in without_accents)
        return " ".join(cleaned.split())
