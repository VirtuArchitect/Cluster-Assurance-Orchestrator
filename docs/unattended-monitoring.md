# Unattended monitoring and durable delivery

## Runtime and safety

Docker Compose starts `monitoring-worker` separately from the API. The worker reads saved connections, forcibly keeps Prism collection read-only, disables SSH/NCC and polls alerts/events every 60 seconds plus inventory every 900 seconds. No browser is required. Browser refreshes now read saved monitoring data; explicit operator collection remains available.

Monitoring and worker singleton locks cover processes on the same shared local volume. Manual and automatic Prism alert collections cannot overlap. This is a single-host appliance design, not multi-host HA. SQLite control/outbox state, WAL and lock files live under the evidence volume; PostgreSQL remains the settings/credentials store. Back up both database and evidence volumes. Do not put the control database on an unsupported network filesystem.

## Self-monitoring

The console shows collection and sender heartbeat ages, collection/inventory failures, configured delivery channels, pending/failed messages and oldest pending age. A configured worker with missing/stale heartbeats is UNHEALTHY; incomplete feeds, failed inventory, sender failures, overdue deliveries or dead messages produce DEGRADED. An active worker is not proof of estate health.

`GET /api/v1/monitoring/worker/ready` exposes only status and returns 503 unless RUNNING. The authenticated `/monitoring/worker/status` and `/monitoring/deliveries` endpoints provide diagnostics. Configure an independent external monitor for readiness: a failed appliance cannot reliably notify about its own total outage. Docker health checks report failure; Docker does not automatically restart a merely unhealthy process.

## Outbound delivery

Set `CAO_ENABLE_ALERTS=true` only after configuring approved destinations. Webhooks require HTTPS with normal certificate validation, block redirects and include a stable `Idempotency-Key`. Non-production loopback HTTP is permitted solely for local delivery tests. Email requires an SMTP relay with STARTTLS, `CAO_SMTP_FROM`, recipient(s), and credentials where required. Passwords and webhook URLs are redacted from settings output.

State changes and delivery jobs commit atomically. Repeated source states are deduplicated; newer unsent states supersede older pending messages. Retry uses exponential backoff (15 seconds, capped at one hour), with eight attempts by default and visible DEAD state on exhaustion. An administrator can retry a dead delivery in the console; changed destinations cannot silently receive previously queued data. Queued jobs and stable identifiers survive process restart. A crash after receiver acceptance can produce a duplicate: this is at-least-once delivery, not exactly once. Receivers should honour the idempotency key / email Message-ID. SMTP acceptance is not inbox delivery or human acknowledgement.

Infrastructure events require current, complete, strict-TLS evidence both when queued and retried. Stale/incomplete evidence and TLS bypass never clear incidents. Collector-failure notifications describe loss of visibility, not cluster failure. Source resolution of A200335 produces recovery-unverified, never automatic recovery certification. Missing source records are never treated as resolution.

Retries and persistence are implemented; escalation policy, recipient acknowledgement, multi-channel escalation and multi-host failover remain outside this increment. Dead-letter or old pending messages must be monitored externally or reviewed by operators. Review queue disk usage and retention as part of production capacity planning.

## Configuration

- `CAO_MONITORING_INTERVAL_SECONDS=60` (minimum 30)
- `CAO_INVENTORY_INTERVAL_SECONDS=900` (minimum 60)
- `CAO_MONITORING_STALE_SECONDS=180` (at least two monitoring intervals)
- `CAO_ALERT_MAX_ATTEMPTS=8`
- `CAO_ALERT_WEBHOOK_URL` or SMTP host/port/from/to configuration
- `CAO_SMTP_PORT=587`; optional username/password; TLS required

Compose enables unattended monitoring. A standalone API deployment must run `python -m app.worker` separately with `CAO_MONITORING_ENABLED=true` and shared settings/evidence storage. Notification destinations remain disabled/unset by default. No real destination is configured or contacted by the automated test suite.

## Verification boundary

Automated tests exercise durable retries, deduplication, dead letters, atomic rollback, heartbeat failures, changed-destination rejection, stale evidence gating, source resolution and enforced read-only collection. A loopback HTTP sink exercises actual failure/retry/acceptance; SMTP protocol calls are tested with a simulated relay. Real relay delivery and enterprise notification routing require operator-provided approved configuration and separate end-to-end acceptance.
