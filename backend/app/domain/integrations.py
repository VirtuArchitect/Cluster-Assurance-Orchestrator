from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class IntegrationState(StrEnum):
    DISABLED = "DISABLED"
    PLANNED = "PLANNED"
    READY = "READY"
    ERROR = "ERROR"


class IntegrationAdapter(BaseModel):
    adapter_id: str
    name: str
    category: str
    state: IntegrationState
    direction: str
    summary: str
    required_settings: list[str] = Field(default_factory=list)
    supported_events: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class IntegrationStatusReport(BaseModel):
    maturity: str
    outbound_enabled: bool
    correlation_key: str
    adapters: list[IntegrationAdapter]


def default_integration_report() -> IntegrationStatusReport:
    adapters = [
        IntegrationAdapter(
            adapter_id="checkmk",
            name="Checkmk",
            category="monitoring",
            state=IntegrationState.PLANNED,
            direction="outbound",
            summary="Map assurance findings into monitored services after UAT mapping.",
            required_settings=["CAO_CHECKMK_URL", "CAO_CHECKMK_SITE", "CAO_CHECKMK_TOKEN"],
            supported_events=["finding.created", "finding.resolved", "run.completed"],
            safety_notes=["Disabled until endpoint allowlists and retry limits are configured."],
        ),
        IntegrationAdapter(
            adapter_id="servicenow",
            name="ServiceNow",
            category="itsm",
            state=IntegrationState.PLANNED,
            direction="outbound",
            summary="Create or update incidents from governed assurance findings.",
            required_settings=["CAO_SERVICENOW_INSTANCE", "CAO_SERVICENOW_CLIENT_ID"],
            supported_events=["finding.critical", "run.failed"],
            safety_notes=["Requires deduplication by run and finding fingerprint before enablement."],
        ),
        IntegrationAdapter(
            adapter_id="email",
            name="Email",
            category="notification",
            state=IntegrationState.PLANNED,
            direction="outbound",
            summary="Send operator summaries for approved schedules and completion events.",
            required_settings=["CAO_SMTP_HOST", "CAO_SMTP_FROM"],
            supported_events=["schedule.summary", "run.completed"],
            safety_notes=["No credentials are stored in source control."],
        ),
        IntegrationAdapter(
            adapter_id="webhook",
            name="Webhook",
            category="notification",
            state=IntegrationState.PLANNED,
            direction="outbound",
            summary="Post signed JSON events to a customer-owned endpoint.",
            required_settings=["CAO_WEBHOOK_URL", "CAO_WEBHOOK_SECRET_REF"],
            supported_events=["finding.created", "finding.resolved", "run.completed"],
            safety_notes=["Payload signing and delivery audit must pass before activation."],
        ),
    ]
    return IntegrationStatusReport(
        maturity="planned",
        outbound_enabled=False,
        correlation_key="run_id + finding_fingerprint",
        adapters=adapters,
    )
