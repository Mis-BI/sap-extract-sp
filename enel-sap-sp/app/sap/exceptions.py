"""Custom errors for SAP automation."""


class SapAutomationError(RuntimeError):
    """Base error for SAP automation failures."""


class SapExportTimeoutError(SapAutomationError):
    """Raised when SAP export file is not detected in time."""
