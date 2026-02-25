"""SAP GUI client and thin session adapter."""
from __future__ import annotations

import logging
import os
import subprocess
import time
import unicodedata

from app.core.settings import Settings
from app.sap.exceptions import SapAutomationError
from app.sap.logon_ui import SapLogonUiAutomation


logger = logging.getLogger(__name__)


class SapSessionFacade:
    """Thin adapter over SAP GUI Scripting session object."""

    def __init__(self, raw_session):
        self._raw = raw_session

    def find(self, element_id: str):
        try:
            return self._raw.findById(element_id)
        except Exception as exc:  # pragma: no cover - runtime COM behavior
            raise SapAutomationError(f"Elemento SAP nao encontrado: {element_id}") from exc

    def exists(self, element_id: str) -> bool:
        try:
            self._raw.findById(element_id)
            return True
        except Exception:
            return False

    def maximize(self) -> None:
        self.find("wnd[0]").maximize()

    def set_text(self, element_id: str, value: str) -> None:
        self.find(element_id).text = value

    def press(self, element_id: str) -> None:
        self.find(element_id).press()

    def select(self, element_id: str) -> None:
        self.find(element_id).select()

    def set_focus(self, element_id: str) -> None:
        self.find(element_id).setFocus()

    def set_caret_position(self, element_id: str, position: int) -> None:
        self.find(element_id).caretPosition = position

    def send_vkey(self, key_code: int) -> None:
        self.find("wnd[0]").sendVKey(key_code)


class SapGuiClient:
    """Creates/attaches SAP GUI session and performs login."""

    def __init__(self, settings: Settings, startup_timeout_seconds: int = 40):
        self._settings = settings
        self._startup_timeout_seconds = startup_timeout_seconds
        self._logon_ui = SapLogonUiAutomation(timeout_seconds=startup_timeout_seconds)

    def connect_and_login(self) -> SapSessionFacade:
        self._ensure_windows()
        win32com_client = self._import_win32com_client()

        sap_gui_auto = self._get_or_start_sap_gui_auto(win32com_client)
        application = self._get_scripting_engine(sap_gui_auto)
        connection = self._open_or_attach_connection(application)
        session = self._wait_for_first_session(connection)

        facade = SapSessionFacade(session)
        self._login_if_required(facade)
        return facade

    @staticmethod
    def _ensure_windows() -> None:
        if os.name != "nt":
            raise SapAutomationError("Automacao SAP GUI so pode ser executada em Windows.")

    @staticmethod
    def _import_win32com_client():
        try:
            import win32com.client  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on platform runtime
            raise SapAutomationError("Dependencia pywin32 nao instalada para SAP GUI scripting.") from exc
        return win32com.client

    def _get_or_start_sap_gui_auto(self, win32com_client):
        try:
            return win32com_client.GetObject("SAPGUI")
        except Exception:
            logger.info("SAP GUI nao encontrado em execucao. Tentando abrir SAP Logon...")
            self._launch_sap_logon()

        deadline = time.monotonic() + self._startup_timeout_seconds
        while time.monotonic() < deadline:
            try:
                return win32com_client.GetObject("SAPGUI")
            except Exception:
                time.sleep(1.0)

        raise SapAutomationError("Nao foi possivel anexar ao SAPGUI. Verifique se o SAP Logon abriu corretamente.")

    def _launch_sap_logon(self) -> None:
        executable = self._settings.sap_logon_executable
        if not executable:
            raise SapAutomationError("SAP_LOGON_EXECUTABLE nao configurado no .env.")
        if not os.path.exists(executable):
            raise SapAutomationError(f"Executavel SAP Logon nao encontrado: {executable}")

        try:
            subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            raise SapAutomationError("Falha ao iniciar o SAP Logon.") from exc

    @staticmethod
    def _get_scripting_engine(sap_gui_auto):
        try:
            return sap_gui_auto.GetScriptingEngine
        except Exception as exc:
            raise SapAutomationError(
                "SAP GUI Scripting nao disponivel. Ative o scripting no cliente e no servidor SAP."
            ) from exc

    def _open_or_attach_connection(self, application):
        logger.info(
            "Conectando no SAP server '%s' e conexao '%s'.",
            self._settings.sap_server_name,
            self._settings.sap_connection_name,
        )

        existing = self._find_connection_by_description(application, self._settings.sap_connection_name)
        if existing is not None:
            logger.info("Conexao SAP reutilizada: %s", self._settings.sap_connection_name)
            return existing

        baseline_connections = self._safe_children_count(application)
        candidates = self._build_connection_open_candidates()
        last_error: Exception | None = None

        for candidate in candidates:
            if not candidate:
                continue
            try:
                connection = application.OpenConnection(candidate, True)
                if connection is not None:
                    logger.info("Conexao SAP aberta por '%s'.", candidate)
                    return connection
            except Exception as exc:  # pragma: no cover - runtime COM behavior
                last_error = exc
                logger.info("OpenConnection falhou para '%s': %s", candidate, exc)

        logger.info("Aplicando fallback de UI: selecao manual de server e conexao no SAP Logon.")
        try:
            self._logon_ui.open_connection(
                server_name=self._settings.sap_server_name,
                connection_name=self._settings.sap_connection_name,
            )
            return self._wait_for_connection_after_ui_click(application, baseline_connections)
        except Exception as exc:
            last_error = exc

        raise SapAutomationError(
            "Nao foi possivel abrir a conexao SAP. "
            f"Verifique SAP_CONNECTION_NAME='{self._settings.sap_connection_name}' "
            f"e SAP_SERVER_NAME='{self._settings.sap_server_name}'."
        ) from last_error

    @staticmethod
    def _children_count(obj) -> int:
        count_attr = getattr(obj.Children, "Count")
        return int(count_attr() if callable(count_attr) else count_attr)

    def _find_connection_by_description(self, application, description: str):
        target = self._normalize(description.replace("...", " "))
        if not target:
            return None

        try:
            total = self._children_count(application)
        except Exception:
            return None

        for idx in range(total):
            try:
                candidate = application.Children(idx)
            except Exception:
                continue
            candidate_desc = self._normalize(str(getattr(candidate, "Description", "")))
            if self._description_matches(candidate_desc, target):
                return candidate

        return None

    def _wait_for_connection_after_ui_click(self, application, baseline_count: int):
        deadline = time.monotonic() + self._startup_timeout_seconds

        while time.monotonic() < deadline:
            current_count = self._safe_children_count(application)
            if current_count > baseline_count and current_count > 0:
                return application.Children(current_count - 1)

            candidate = self._find_connection_by_description(application, self._settings.sap_connection_name)
            if candidate is not None:
                return candidate

            time.sleep(0.5)

        raise SapAutomationError("Timeout aguardando conexao SAP apos clique no SAP Logon.")

    def _build_connection_open_candidates(self) -> list[str]:
        values = []
        raw = self._settings.sap_connection_name.strip()
        if raw:
            values.append(raw)
            without_ellipsis = raw.replace("...", " ").strip()
            if without_ellipsis and without_ellipsis != raw:
                values.append(without_ellipsis)

        # Last attempt through OpenConnection with server name in case instance names differ.
        server = self._settings.sap_server_name.strip()
        if server:
            values.append(server)

        dedup: list[str] = []
        seen = set()
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(value)
        return dedup

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(text))
        without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in without_accents)
        return " ".join(cleaned.split())

    @staticmethod
    def _description_matches(candidate_desc: str, target: str) -> bool:
        if not candidate_desc or not target:
            return False
        if target in candidate_desc:
            return True

        target_tokens = [token for token in target.split() if token]
        if not target_tokens:
            return False
        return all(token in candidate_desc for token in target_tokens[:3])

    @staticmethod
    def _safe_children_count(obj) -> int:
        try:
            return SapGuiClient._children_count(obj)
        except Exception:
            return 0

    def _wait_for_first_session(self, connection):
        deadline = time.monotonic() + self._startup_timeout_seconds
        while time.monotonic() < deadline:
            try:
                total = self._children_count(connection)
                if total > 0:
                    return connection.Children(0)
            except Exception:
                pass
            time.sleep(0.5)

        raise SapAutomationError("Timeout aguardando abertura da sessao SAP.")

    def _login_if_required(self, session: SapSessionFacade) -> None:
        user_field = "wnd[0]/usr/txtRSYST-BNAME"
        pwd_field = "wnd[0]/usr/pwdRSYST-BCODE"
        lang_field = "wnd[0]/usr/txtRSYST-LANGU"
        client_field = "wnd[0]/usr/txtRSYST-MANDT"

        if not session.exists(user_field):
            logger.info("Sessao SAP ja autenticada.")
            return

        logger.info("Realizando login SAP com credenciais do .env")
        session.set_text(user_field, self._settings.sap_username)
        session.set_text(pwd_field, self._settings.sap_password)

        if self._settings.sap_client and session.exists(client_field):
            session.set_text(client_field, self._settings.sap_client)

        if self._settings.sap_language and session.exists(lang_field):
            session.set_text(lang_field, self._settings.sap_language)

        session.send_vkey(0)
