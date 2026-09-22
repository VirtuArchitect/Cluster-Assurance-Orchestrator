# Cluster Assurance Orchestrator

Independent operational health assurance for Nutanix environments.

This repository is being prepared from the design work package as a controlled lab-first build. The first delivery should validate read-only Prism discovery, health status handling, evidence capture, audit behavior, and demo-safe UX before any NCC or SSH execution is introduced.

Cluster Assurance Orchestrator is an independent project and is not affiliated with, endorsed by or supported by Nutanix, Inc. Nutanix, AHV, AOS, NCC, Prism Central and Prism Element are trademarks or registered trademarks of Nutanix, Inc. in the United States and other countries.

## Current Stage

- Scope: lab-validated read-only collection, operator console and gated production-readiness scaffolds with local auth/RBAC.
- Lab posture: read-only API validation first.
- Credential handling: local-only configuration; never commit real credentials.
- NCC posture: allowlisted planning only; SSH execution is intentionally unavailable.
- Integration posture: email and webhook alert hooks are gated until evidence is trustworthy; Checkmk and ServiceNow remain planned.

## Local Configuration

Copy `config/local.env.example` to `config/local.env` on the development machine and fill in local values. The real `config/local.env` file is ignored by Git.

## Planning Artifacts

- `docs/lab-validation-plan.md` defines the staged lab validation approach.
- `docs/test-matrix.md` defines the first test coverage matrix.
- `docs/traceability.md` maps initial work-package requirements to planned implementation evidence.

## Backend Development

Install dependencies in a local virtual environment, then run:

```powershell
pytest
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Initial endpoints:

- `GET /api/v1/health`
- `GET /api/v1/support/status`
- `GET /api/v1/catalogue`
- `POST /api/v1/runs/demo`
- `POST /api/v1/lab/discovery`
- `POST /api/v1/lab/inventory-runs`
- `GET /api/v1/lab/inventory-runs/latest`
- `POST /api/v1/health-runs/manual`
- `GET /api/v1/health-runs/history`
- `GET /api/v1/schedules/preview/default`
- `POST /api/v1/schedules/preview`
- `GET /api/v1/schedules`
- `POST /api/v1/schedules`
- `POST /api/v1/schedules/run-due`
- `POST /api/v1/schedules/{schedule_id}/run-now`
- `GET /api/v1/schedules/runs/history`
- `GET /api/v1/ncc/profiles`
- `POST /api/v1/ncc/plan`
- `POST /api/v1/ncc/parse`
- `GET /api/v1/evidence/manifest/latest`
- `GET /api/v1/evidence/retention`
- `POST /api/v1/evidence/archive/export`
- `POST /api/v1/evidence/restore-drill`
- `GET /api/v1/integrations/status`
- `GET /api/v1/alerts/status`
- `GET /api/v1/security/readiness`

Except for `/api/v1/health` and `/api/v1/auth/login`, operational endpoints require a bearer session. Admin-only endpoints include RBAC mutation, connection management, audit viewing and evidence retention/archive controls.

Run read-only lab discovery from local ignored configuration:

```powershell
.\.venv\Scripts\python.exe -m app.cli.discover_lab --env-file config/local.env
```

Use `CAO_TLS_MODE=insecure_skip_verify` only for lab certificates that cannot yet be validated by a custom trust bundle. Evidence from that mode is labelled lab-only.

Run a read-only lab inventory collection:

```powershell
.\.venv\Scripts\python.exe -m app.cli.run_inventory --env-file config/local.env
```

Inventory runs store raw response bodies under `evidence/lab/raw/<run-id>/` and write a normalized summary evidence file. Failed, empty, partial or unparsable mandatory collectors produce `UNKNOWN`, never `HEALTHY`.

Manual and scheduled health runs now use the saved Prism connections for domain-specific read-only collectors:

- inventory: cluster inventory and version evidence
- storage: storage container/pool-facing API evidence
- hardware: host/node-facing API evidence
- network: subnet/network-facing API evidence
- capacity: cluster payload evidence for later headroom calculations

The domain collectors record route, method, HTTP status, item count and raw artifact references. They prove coverage first; deeper semantic thresholds for storage utilization, hardware faults, NIC/link state and capacity forecasting should be validated per Prism payload before being treated as production health rules.

After a lab health run, inspect the saved Prism response shapes without printing full raw payload values:

```powershell
.\.venv\Scripts\python.exe -m app.cli.inspect_evidence_schema --env-file config/local.env
```

Use `--json` for a machine-readable summary, or `--evidence-file <path>` to inspect a specific inventory run. The report lists top-level keys, entity array location, common entity keys and candidate health/capacity fields for each collector artifact.

## Frontend Development

From `frontend/`, install npm dependencies and run:

```powershell
npm run dev
```

The operator console reads the latest local inventory evidence from the API and can trigger a read-only manual health run when the signed-in user has `run_read_only_inventory`.

Schedules are persisted in the local admin database. The scheduler runner records run history, enforces occurrence idempotency and uses short-lived cluster locks before calling the same read-only inventory collector used by manual runs.

The Phase 5 NCC gate is planning-only. It exposes allowlisted command profiles and parser behavior, but it does not implement SSH transport or execute NCC.

The remaining phase surfaces expose production-readiness contracts without over-claiming maturity:

- Evidence manifests hash normalized and raw collector artifacts.
- Evidence retention, archive export and restore-drill APIs provide local operational backup controls.
- Integration status lists planned adapters; alert status gates email/webhook delivery until evidence is trusted.
- Security readiness reports RBAC permissions and open gates for TLS, UAT and external backup operations.
- The console uses a ZTF-suite visual treatment and shared suite mark while keeping Cluster Assurance as the product identity.

## Docker Deployment

The Docker profile builds the React console and serves it from the FastAPI container. It persists evidence, RBAC, schedules, connection metadata, sealed secrets and audit events in a Docker volume mounted at `/data`.

```powershell
Copy-Item config\appliance.env.example config\appliance.env
docker compose up --build -d
```

Open `http://127.0.0.1:8080/`.

Set a strong `CAO_AUTH_SECRET` in `config/appliance.env` before using this outside disposable local testing. Prism connections can be added through **Settings > Connections**, so endpoint secrets do not need to be stored in the Compose file.

## Appliance Bundle

Create a downloadable appliance-style ZIP:

```powershell
.\scripts\build-appliance.ps1 -Version 0.1.0
```

The bundle is written under `dist-appliance/` and includes:

- Docker Compose deployment files
- appliance environment template
- appliance runbook
- manifest and SHA-256 checksum
- Docker image tar when Docker is available and `-SkipDockerImage` is not used

See `docs/appliance.md` for install, air-gapped transfer and backup guidance.

## GitHub Publication

The repository includes GitHub Actions CI for backend tests, frontend build and Docker image build. See `docs/github-publication.md` for first-publish, branch/PR and release-artifact steps.

This local folder is not currently initialized as a Git repository. To publish, initialize it and add the target GitHub remote, or provide the intended `owner/repository` target so the source can be pushed deliberately without guessing.
