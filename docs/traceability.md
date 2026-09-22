# Requirement Traceability

This file maps the initial design baseline to implementation and validation evidence. It should be updated with code paths, test names and evidence artifacts as the solution is built.

| Requirement | Planned implementation | Planned verification | Status |
| --- | --- | --- | --- |
| Independent product identity and trademark boundary | README notice and ZTF-suite UI treatment with Cluster Assurance naming | Visual review and content check | Implemented |
| Read-only first lab validation | Configuration flag and adapter guardrails | Lab validation tests and logs | Implemented |
| Failed collection is `UNKNOWN`, not healthy | Health evaluation rules engine | Unit tests for mandatory collector failures | Implemented |
| Raw vendor response retained alongside normalized result | Evidence artifact service and latest manifest endpoint | Manifest hash and artifact reference tests | Implemented |
| Prism Central discovery and inventory | Nutanix adapter capability matrix and read-only collectors | Contract tests with approved fixtures | Planned |
| Prism Element fallback for defined gaps | Explicit fallback adapter methods | Capability-matrix tests | Planned |
| Lab discovery evidence | Read-only discovery CLI and `/api/v1/lab/discovery` endpoint | 14 unit tests plus `evidence/lab/lab-discovery-20260922T073520Z.json` | Lab evidence captured |
| Read-only inventory run | Prism Central cluster-list and Prism Element cluster-detail collectors with local raw artifacts | 18 unit tests plus `evidence/lab/inventory-run-20260922T074251Z.json` | Lab evidence captured; overall UNKNOWN due Prism Element HTTP 401 |
| Operator console latest evidence view | API reader for latest local inventory evidence and React dashboard, estate, run, evidence and audit views | 21 unit tests, frontend build and local smoke check | Implemented |
| Runtime support status panel | Support status API and dashboard panel for mode, config source, evidence path, last run age/type and collector failures | Unit tests, frontend build and local smoke check | Implemented |
| Scheduling and concurrency preview | Immutable profile version, schedule preview, idempotency keys and active cluster lock planning | Unit tests plus UI/API smoke check | Implemented |
| Scheduled health execution | Persisted schedule runner with run history, idempotency and cluster locks | Unit tests for run-now history/audit plus API smoke check | Implemented for synchronous local runner |
| NCC constrained execution | Allowlisted command profiles, parser, planning API and no SSH transport | Negative tests for shell input, unknown output and FAIL parsing | Implemented as gated planning only |
| No arbitrary browser shell access | API schema excludes command text and target host input | Injection and authorization tests | Implemented for NCC planning surface |
| Role-based access | Server-side authorization model | RBAC readiness route and API tests | Implemented for administrative, evidence and run-control APIs |
| Evidence manifest with hashes | Latest manifest generator | SHA-256 verification tests | Implemented |
| Evidence retention and backup controls | Retention policy, archive export and restore-drill endpoints | Unit tests for archive hash and restore drill | Implemented locally; external backup procedure still required |
| Audit on material actions | Persistent local audit table and audit page | API tests for auth, RBAC, connections, schedules, evidence and alert events | Implemented |
| Demo mode cannot contact infrastructure | Demo provider separated from real adapters | Tests proving no external calls in demo mode | Implemented |
| Integration readiness | Checkmk, ServiceNow, email and webhook contracts | API tests for disabled planned adapters and gated alert status | Email/webhook hooks gated; Checkmk and ServiceNow planned |
| Production readiness gates | Security readiness endpoint and console page | API tests for TLS/read-only/RBAC/backup gate status | Implemented as readiness model |
| Requirement-to-test traceability | This file plus test report references | Review before release milestones | In progress |

## Maturity Labels

Use these labels consistently in UI, README and release notes:

- `simulated`: uses synthetic data and cannot contact infrastructure.
- `lab validated`: tested against the local lab with documented evidence.
- `controlled UAT`: validated with approved operators and agreed scope.
- `production approved`: approved through security, operations and product readiness review.
