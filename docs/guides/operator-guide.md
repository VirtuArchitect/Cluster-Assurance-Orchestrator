# Operations Console User Guide

Understand status, freshness and the immediate-action workflow without false health claims.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Start with source confidence

1. Dashboard separates PE cluster operations from the PC management plane. Read source age, feed coverage and connection trust before interpreting totals. PE and PC observations can describe the same fault and are not deduplicated incident counts.

2. Monitoring posture requires complete feeds and evidence within the current freshness window (two minutes). Saved evidence remains visible when unconfirmed. Inventory evidence has its own timestamp and is not refreshed by collecting alerts.

3. The traffic-light donut counts sources, not incidents. Red means a source reported critical alerts; amber means warning alerts; green means no critical/warning alerts in fresh complete evidence; grey means unknown or stale. Green does not prove recovery.

## 2. Work the immediate-action queue

1. Review critical priorities first, then warnings and recovery follow-ups. Filter by source, action type or affected entity and open the exact incident. Establish user/service impact independently.

2. Recovery follow-ups remain actionable after Prism resolution. A recovery entry is not an additional source alert. An unavailable diagnostics feed means recovery is unverified rather than confirmed blocked or complete.

3. Read Operator Triage for evidence gaps and next steps. Collection-count changes do not establish configuration or service-state changes. Escalate conflicting observations with timestamps and source identity.

## 3. Interpret the other pages

1. Cluster Estate preserves last-known entries when inventory collection fails. CURRENT means an entry belongs to the saved collection, not continuous availability; check evidence age. Do not interpret inventory presence as cluster health.

2. Health Runs and Collection Diagnostics describe read-only API requests and saved results. COLLECTED is a response outcome. Authentication failures group by endpoint; investigate access once and review the individual checks.

3. Schedules distinguish preview from recorded execution. Evidence separates hashes, retention and TLS trust from production acceptance. Settings shows saved test and account configuration, not continuous access validation.

## 4. Close and hand over

1. Record the symptom, source alert/check IDs, affected service, source and observed times, freshness, collection errors and evidence hashes. Separate observations, likely contributors and verified causes.

2. Close only when the source status, deployment/prerequisite checks and independent service validation meet the incident recovery criteria. A manually resolved alert is not sufficient.

3. Hand over remaining actions, owners, next review time and escalation condition. Share only approved sanitised extracts; raw evidence may contain private names, addresses and identifiers.

Source basis: frontend/src/operatorDashboard.tsx, frontend/src/operational.ts, frontend/src/pageGuidance.tsx
