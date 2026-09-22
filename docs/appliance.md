# Cluster Assurance Orchestrator Appliance

This appliance profile packages the API and operator console into one container with a persistent data volume. It is intended for lab validation, controlled UAT and internal operational-support workflows.

It is not an official Nutanix product and does not make production-readiness claims by itself. Evidence gathered with `CAO_TLS_MODE=insecure_skip_verify` is labelled lab-only.

## Contents

- `cluster-assurance-orchestrator:<version>` Docker image, when built by `scripts/build-appliance.ps1`.
- `docker-compose.yml` for a one-container deployment.
- `config/appliance.env.example` as the operator-editable configuration template.
- Persistent `/data` volume for evidence, RBAC, schedules, connection metadata, sealed secrets and audit events.

## Build

From a development machine with Docker:

```powershell
.\scripts\build-appliance.ps1 -Version 0.1.0
```

The script writes:

- `dist-appliance/cluster-assurance-orchestrator-<version>-appliance.zip`
- `dist-appliance/cluster-assurance-orchestrator-<version>-appliance.zip.sha256`

Use `-SkipDockerImage` to create a lightweight bundle without an image tar.

## Install

1. Extract the appliance ZIP on the target host.
2. Copy `config/appliance.env.example` to `config/appliance.env`.
3. Set `CAO_AUTH_SECRET` to a long random value.
4. Set `CAO_BOOTSTRAP_ADMIN_PASSWORD` before first start, or rotate the admin password immediately after first sign-in.
5. For labs with self-signed Prism certificates, set `CAO_TLS_MODE=insecure_skip_verify`; keep `strict` for trusted environments.
6. Start the appliance:

```powershell
docker compose up -d
```

Open `http://<host>:8080/`.

## Air-Gapped Transfer

For disconnected environments:

1. Build the appliance ZIP on the development machine.
2. Verify the ZIP SHA-256 on the development machine.
3. Transfer the ZIP and `.sha256` file to the jump host.
4. Verify SHA-256 on the jump host.
5. Transfer the ZIP and `.sha256` file to the appliance host.
6. Verify SHA-256 again before extraction.
7. Load the image if the tar is present:

```powershell
docker load -i .\cluster-assurance-orchestrator-0.1.0-image.tar
```

8. Start with Docker Compose.

## Backup

The named Docker volume contains local state. Back it up before upgrades:

```powershell
docker run --rm -v cluster-assurance-orchestrator_cao-data:/data -v ${PWD}:/backup alpine tar czf /backup/cao-data-backup.tgz -C /data .
```

Also use the in-app evidence archive and restore-drill controls before making release claims.

## Update Boundary

The appliance remains read-only against Prism by default:

- `CAO_READ_ONLY_MODE=true`
- `CAO_ENABLE_NCC=false`
- `CAO_ENABLE_SSH=false`

Do not enable mutating operations in this appliance profile without a separate design, UAT plan and rollback procedure.
