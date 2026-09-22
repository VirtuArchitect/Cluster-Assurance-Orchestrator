from __future__ import annotations

from app.domain.integrations import IntegrationStatusReport, default_integration_report


def integration_status() -> IntegrationStatusReport:
    return default_integration_report()
