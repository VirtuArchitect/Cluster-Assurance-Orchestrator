# Controlled Production-Test Quick Start

Prepare an isolated, traceable evaluation and establish its safety boundary.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Establish the test boundary

1. Nominate a test lead, incident owner and rollback approver. Agree the PE/PC versions, maintenance window, data classification and acceptance criteria before connecting real systems.

2. This candidate is not production approved. Start in a controlled environment with read-only Prism permissions, strict TLS, SSH disabled and NCC execution disabled. Do not broaden privileges to make a failing test pass.

3. Use an immutable image or appliance artifact from a reviewed clean commit. Record version, full revision, build time, image digest and archive SHA-256. A matching version label alone is insufficient.

## 2. Prepare the appliance

1. Follow the appliance runbook and configure unique secrets through the deployment environment, never in chat or documentation. Replace every supplied development default before testing. Keep the authentication secret and database credentials in approved secret storage.

2. Protect the console with an approved HTTPS reverse proxy and network restrictions before remote use. The default container port is HTTP; it does not provide a production ingress or certificate lifecycle.

3. Back up database and evidence volumes plus the deployment configuration. Verify a restore in a separate environment. A successful backup creation is not proof that restore works.

## 3. Connect and collect

1. Open Settings > Connections. Configure separate Prism Element and Prism Central endpoints using pe.example.invalid and pc.example.invalid as documentation examples only. Validate trusted certificates and least-privilege credentials.

2. Run the connection test, then collect inventory from Health Runs. Separately collect Prism alerts and events from the dashboard or Prism Incidents. A passed connection test is not a collection result.

3. Inspect all configured sources and feed completeness. Confirm timestamp and TLS mode. A missing, stale, failed or incomplete source remains unknown; preserve its last-known evidence.

## 4. Record the acceptance result

1. Check Settings > About. UI and API versions/revisions must match, source must be clean, revision must be known and artifact checksums must match the approved package. Record a mismatch as a test failure.

2. Confirm /api/v1/health reports the expected build and effective read-only mode with NCC and SSH disabled. Its status=ok concerns the app response, not the Nutanix estate.

3. Record functional results, permissions exercised, observed limitations and rollback evidence in the test record. Only the accountable approver may accept the candidate for the agreed scope.

Source basis: docs/appliance.md, backend/app/api/routes.py, backend/app/core/config.py
