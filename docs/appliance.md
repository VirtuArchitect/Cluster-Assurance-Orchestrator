# Cluster Assurance Orchestrator Appliance

This appliance profile packages the API/operator console with a Postgres settings database. It is intended for lab validation, controlled UAT and internal operational-support workflows.

It is not an official Nutanix product and does not make production-readiness claims by itself. Evidence gathered with `CAO_TLS_MODE=insecure_skip_verify` is labelled lab-only.

## Contents

- `cluster-assurance-orchestrator:<version>` Docker image, when built by `scripts/build-appliance.ps1`.
- `docker-compose.yml` for the API/console and Postgres deployment.
- `config/appliance.env.example` as the operator-editable configuration template.
- Persistent Postgres volume for RBAC, schedules, connection metadata, sealed secrets and audit events.
- Persistent `/data` volume for evidence, archives and restore-drill artifacts.

## Build

From a development machine with Docker:

```powershell
.\scripts\build-appliance.ps1 -Version 0.1.0
```

The script writes:

- `dist-appliance/cluster-assurance-orchestrator-<version>-appliance.zip`
- `dist-appliance/cluster-assurance-orchestrator-<version>-appliance.zip.sha256`

Use `-SkipDockerImage` to create a lightweight bundle without an image tar.

The same bundle can be built in GitHub Actions:

1. Open **Actions > Appliance Bundle**.
2. Choose **Run workflow**.
3. Set the version.
4. Choose whether to include the Docker image tar.
5. Download the generated appliance artifact from the workflow run.

For release builds, push a `v*` tag or select `create_release` during a manual run. The workflow attaches the ZIP and `.sha256` file to the GitHub Release.

## Install

1. Extract the appliance ZIP on the target host.
2. Copy `config/appliance.env.example` to `config/appliance.env`.
3. Set `CAO_AUTH_SECRET` to a long random value.
4. Set `POSTGRES_PASSWORD` and the password portion of `CAO_ADMIN_DATABASE_URL` to the same strong value.
5. Set `CAO_BOOTSTRAP_ADMIN_PASSWORD` before first start, or rotate the admin password immediately after first sign-in.
6. For labs with self-signed Prism certificates, set `CAO_TLS_MODE=insecure_skip_verify`; keep `strict` for trusted environments.
7. Start the appliance:

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

Use **Settings > Storage** to create and download an on-demand Postgres logical export from the console. The named Docker volumes also contain local state and should be backed up before upgrades:

```powershell
docker run --rm --volumes-from cluster-assurance-orchestrator -v ${PWD}:/backup alpine tar czf /backup/cao-data-backup.tgz -C /data .
docker compose exec -T postgres pg_dump -U cao -d cao > cao-settings-backup.sql
```

Also use the in-app evidence archive and restore-drill controls before making release claims.

## Update Boundary

The appliance remains read-only against Prism by default:

- `CAO_READ_ONLY_MODE=true`
- `CAO_ENABLE_NCC=false`
- `CAO_ENABLE_SSH=false`

Do not enable mutating operations in this appliance profile without a separate design, UAT plan and rollback procedure.
