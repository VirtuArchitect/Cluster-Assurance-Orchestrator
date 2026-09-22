# Nutanix Capability Matrix

This matrix records what the application is allowed to claim for the lab. A capability is not considered supported until it has a source, a probe or fixture, and a test or evidence artifact.

| Capability | Interface | Probe | Status | Evidence |
| --- | --- | --- | --- | --- |
| Prism Central HTTPS reachability | Prism Central | `GET /` | Lab reachable, HTTP 200 | `evidence/lab/lab-discovery-20260922T073520Z.json`, SHA-256 `ae1704be44f3abffef3f19c9fcd6c4bc7e0166bbdc468cd78734e08e99895ddf` |
| Prism Central v3 cluster-list route presence | Prism Central | `GET /api/nutanix/v3/clusters/list` | Inconclusive, HTTP 400 from GET-only probe | `evidence/lab/lab-discovery-20260922T073520Z.json`, SHA-256 `ae1704be44f3abffef3f19c9fcd6c4bc7e0166bbdc468cd78734e08e99895ddf` |
| Prism Element HTTPS reachability | Prism Element | `GET /` | Lab reachable, HTTP 200 | `evidence/lab/lab-discovery-20260922T073520Z.json`, SHA-256 `ae1704be44f3abffef3f19c9fcd6c4bc7e0166bbdc468cd78734e08e99895ddf` |
| Prism Element cluster details | Prism Element | `GET /PrismGateway/services/rest/v2.0/cluster/` | Protected route present, HTTP 401 | `evidence/lab/lab-discovery-20260922T073520Z.json`, SHA-256 `ae1704be44f3abffef3f19c9fcd6c4bc7e0166bbdc468cd78734e08e99895ddf` |
| Inventory normalization | Internal | Prism Central POST cluster-list and Prism Element GET cluster details | Prism Central normalized 2 clusters; Prism Element remains UNKNOWN due HTTP 401 | `evidence/lab/inventory-run-20260922T074251Z.json`, SHA-256 `9e4ff86406224201849c4c8c4aeb7cb51dd86729e53a1e4fc2f76219c481f1e9` |
| Storage domain collection | Prism Central / Prism Element | PC `POST /api/nutanix/v3/storage_containers/list`; PE `GET /PrismGateway/services/rest/v2.0/storage_containers/` | Implemented as read-only coverage collector with raw artifacts and item counts | Unit test `test_domain_collectors_use_configured_prism_connections` |
| Hardware domain collection | Prism Central / Prism Element | PC `POST /api/nutanix/v3/hosts/list`; PE `GET /PrismGateway/services/rest/v2.0/hosts/` | Implemented as read-only coverage collector with raw artifacts and item counts | Unit test `test_domain_collectors_use_configured_prism_connections` |
| Network domain collection | Prism Central / Prism Element | PC `POST /api/nutanix/v3/subnets/list`; PE `GET /PrismGateway/services/rest/v2.0/networks/` | Implemented as read-only coverage collector with raw artifacts and item counts | Unit test `test_domain_collectors_use_configured_prism_connections` |
| Capacity domain collection | Prism Central / Prism Element | PC `POST /api/nutanix/v3/clusters/list`; PE `GET /PrismGateway/services/rest/v2.0/cluster/` | Implemented as read-only coverage collector; semantic headroom thresholds remain planned | Unit test `test_domain_collectors_use_configured_prism_connections` |
| NCC selected daily profile | SSH/NCC | Allowlisted command profile `full-run-all` -> `ncc health_checks run_all` | Gate implemented; transport not implemented | Unit tests and `/api/v1/ncc/profiles`, `/api/v1/ncc/plan`, `/api/v1/ncc/parse` |
| Evidence manifest | Internal | Latest inventory evidence reader | Implemented for local evidence files and raw artifact references | Unit tests and `/api/v1/evidence/manifest/latest` |
| Runtime support status | Internal | Support status endpoint | Implemented for mode, config source, evidence path, last run age/type and collector failures | Unit tests and `/api/v1/support/status` |
| Schedule runner | Internal | Persisted schedules, idempotency key and lock tables | Implemented for run-now and due-run execution through read-only inventory path | Unit tests and `/api/v1/schedules/run-due`, `/api/v1/schedules/{id}/run-now`, `/api/v1/schedules/runs/history` |
| Evidence backup controls | Internal | Retention, archive export and restore drill APIs | Implemented for local evidence archive and JSON parse drill; external backup remains operational | Unit tests and `/api/v1/evidence/retention`, `/api/v1/evidence/archive/export`, `/api/v1/evidence/restore-drill` |
| Integration readiness | Internal | Disabled adapter catalogue and gated alert status | Email/webhook hooks are gated until evidence is trusted; Checkmk and ServiceNow planned | Unit tests and `/api/v1/integrations/status`, `/api/v1/alerts/status` |
| Security readiness | Internal | Gate and RBAC matrix | Bearer auth/RBAC implemented; TLS, external backup and controlled UAT remain gates | Unit tests and `/api/v1/security/readiness` |

## Rules

- Do not treat route presence as semantic support.
- POST-based read-list operations are allowed only inside authenticated, read-only health runs where raw artifacts and tests exist.
- Do not add an adapter method without a capability row and a test or evidence artifact.
- A failed collector produces `UNKNOWN`, never `HEALTHY`.
- Insecure TLS evidence is lab-only and cannot support production-readiness claims.

## Phase 2 Lab Evidence

The latest Phase 2 inventory run normalized these Prism Central cluster records:

| Source | Name | Version | State |
| --- | --- | --- | --- |
| Prism Central | `DEV_LAB` | `6.10.1.14` | `COMPLETE` |
| Prism Central | `PC_EXAMPLE` | `2024.3.1.14` | `COMPLETE` |

The Prism Element cluster endpoint returned HTTP `401`, so the overall run status remained `UNKNOWN`. This is intentional: a partial inventory result is not allowed to produce a healthy estate status.

## Phase 5 NCC Gate

The NCC gate currently supports one reviewed profile:

| Profile | Command | Status |
| --- | --- | --- |
| `full-run-all` | `ncc health_checks run_all` | Allowlisted for planning only |

Transport execution is not implemented. The browser and API accept a profile identifier, not command text. Unknown profile identifiers, including strings that look like shell commands, are rejected.

## Remaining Phase Contracts

The current implementation exposes readiness contracts for the remaining phases without enabling live side effects:

- Integrations are listed as planned; email/webhook alert hooks remain gated until trusted evidence is available.
- RBAC permissions are enforced on administrative, evidence and run-control APIs.
- Evidence manifests hash local evidence and raw collector references.
- Production approval remains blocked by explicit TLS, external backup procedures and controlled-UAT gates.
