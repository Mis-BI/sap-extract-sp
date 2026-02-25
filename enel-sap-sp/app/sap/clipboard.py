"""Clipboard helpers for IW59 value upload."""
from __future__ import annotations

import os

from app.sap.exceptions import SapAutomationError


class WindowsClipboardService:
    """Writes values to Windows clipboard."""

    def copy_lines(self, values: list[str]) -> None:
        payload = "\r\n".join(values)
        if os.name != "nt":
            raise SapAutomationError("Automacao SAP GUI requer Windows para uso da area de transferencia.")

        try:
            import win32clipboard  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on platform runtime
            raise SapAutomationError("Dependencia pywin32 nao instalada para acesso ao clipboard.") from exc

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(payload, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
