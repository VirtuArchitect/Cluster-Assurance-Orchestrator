# Unattended monitoring validation - 22 November 2026

Local draft candidate: 0.2.0-rc.1, dirty working branch. Not an immutable release or production certification.

## Implemented

- Separate Compose worker polls read-only Prism alerts/events every 60 seconds and inventory every 900 seconds, independent of browser activity.
- Persistent worker/sender heartbeats and source/inventory error reporting; authenticated diagnostics, 503 readiness failure, singleton/cross-process locks and administrator retry controls.
- Atomic state transitions and outbox jobs, stable identifiers, duplicate suppression, superseding stale pending states, bounded retry/backoff, dead-letter visibility and destination-change protection.
- Strict TLS webhook validation, blocked redirects and STARTTLS SMTP transport. Infrastructure notification confidence is checked on enqueue and retry. A200335 source resolution remains recovery-unverified.
- Removed the requested header badge while preserving contextual evidence/TLS limitations.

## Verification

- 143 backend tests passed, including 15 monitoring-control tests and the typed empty PC storage envelope regression. Existing Starlette/httpx deprecation warning remains.
- 14 frontend tests passed. TypeScript/Vite production build and application Docker build passed. Compose safety settings and git diff whitespace check passed.
- Actual loopback HTTP delivery failed once with 503 and then succeeded with the same idempotency key. SMTP TLS/message handling was verified with a simulated relay. No external notification recipient was contacted.
- Live unattended dev collection at 13:59:13 CET: all four PE/PC alert and event feeds complete; 10/10 inventory collectors successful; read-only true, SSH false, NCC false. Multiple autonomous collection cycles were observed before and after worker replacement.
- Initial PC storage inventory correctly reported UNKNOWN because the typed zero-result response omitted data. The parser now accepts only the exact typed zero-result envelope with explicit non-error/non-truncated metadata. A worker-driven inventory retry then verified all collectors. A zero PC storage count does not prove an absence of PE storage or complete storage health.
- Worker readiness returned RUNNING/HTTP 200 and Docker worker health was healthy. The running UI showed RUNNING, heartbeat ages, notification configuration and queue diagnostics; header badge removal and saved-evidence refresh were visually verified.

## Remaining acceptance boundaries

- External notifications are disabled and have no configured recipient. Production webhook/SMTP routing and inbox/on-call acknowledgement require approved configuration and separate acceptance.
- Dev evidence bypasses TLS verification; infrastructure notifications remain gated. No TLS protection was weakened by this work.
- Single-host SQLite outbox/control state is not multi-host HA. Independent external readiness monitoring remains required to detect complete appliance loss. Review queue disk usage/retention and operational escalation policies.
- No PE/PC infrastructure changes, new runtime dependencies, commits or publication were performed.
