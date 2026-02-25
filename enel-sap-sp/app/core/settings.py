"""Application settings loaded from .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _as_int(raw: str | None, default: int) -> int:
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _resolve_project_path(raw: str, project_root: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


@dataclass(frozen=True)
class Settings:
    """Runtime settings for API and SAP automation."""

    sap_username: str
    sap_password: str
    sap_client: str
    sap_language: str
    sap_server_name: str
    sap_connection_name: str
    sap_logon_executable: str
    sap_export_dir: Path
    sap_zucrm_export_glob: str
    sap_iw59_export_glob: str
    sap_export_timeout_seconds: int
    sap_f3_max_presses: int
    sap_qmart: str
    sap_variation: str
    sap_transaction_zucrm: str
    sap_transaction_iw59: str
    log_level: str
    log_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[2]
        export_default = project_root / "downloads"
        log_default = project_root / "logs" / "sap_automation.log"

        export_dir_raw = os.getenv("SAP_EXPORT_DIR", str(export_default)).strip() or str(export_default)
        log_file_raw = os.getenv("LOG_FILE", str(log_default)).strip() or str(log_default)

        return cls(
            sap_username=os.getenv("SAP_USERNAME", "").strip(),
            sap_password=os.getenv("SAP_PASSWORD", "").strip(),
            sap_client=os.getenv("SAP_CLIENT", "").strip(),
            sap_language=os.getenv("SAP_LANGUAGE", "PT").strip() or "PT",
            sap_server_name=os.getenv("SAP_SERVER_NAME", "00 SAP ERP").strip() or "00 SAP ERP",
            sap_connection_name=(
                os.getenv("SAP_CONNECTION_NAME", "H181 RP1 ENEL SP CCS Produção (without SSO)").strip()
                or "H181 RP1 ENEL SP CCS Produção (without SSO)"
            ),
            sap_logon_executable=os.getenv(
                "SAP_LOGON_EXECUTABLE",
                r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            ).strip(),
            sap_export_dir=_resolve_project_path(export_dir_raw, project_root),
            sap_zucrm_export_glob=os.getenv("SAP_ZUCRM_EXPORT_GLOB", "sap_gov_sp*.XLSX").strip() or "sap_gov_sp*.XLSX",
            sap_iw59_export_glob=os.getenv("SAP_IW59_EXPORT_GLOB", "brs_sap_gov_sp*.XLSX").strip() or "brs_sap_gov_sp*.XLSX",
            sap_export_timeout_seconds=_as_int(os.getenv("SAP_EXPORT_TIMEOUT_SECONDS"), 180),
            sap_f3_max_presses=_as_int(os.getenv("SAP_F3_MAX_PRESSES"), 20),
            sap_qmart=os.getenv("SAP_QMART", "ov").strip() or "ov",
            sap_variation=os.getenv("SAP_VARIATION", "/abap ov2").strip() or "/abap ov2",
            sap_transaction_zucrm=os.getenv("SAP_TRANSACTION_ZUCRM", "zucrm_039").strip() or "zucrm_039",
            sap_transaction_iw59=os.getenv("SAP_TRANSACTION_IW59", "iw59").strip() or "iw59",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper().strip() or "INFO",
            log_file=_resolve_project_path(log_file_raw, project_root),
        )

    def validate_sap_credentials(self) -> None:
        missing = []
        if not self.sap_username:
            missing.append("SAP_USERNAME")
        if not self.sap_password:
            missing.append("SAP_PASSWORD")
        if missing:
            missing_str = ", ".join(missing)
            raise ValueError(f"Variaveis obrigatorias ausentes no .env: {missing_str}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings.from_env()
