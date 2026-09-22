# GitHub Publication Runbook

This project should be published like an operator-facing infrastructure tool: source first, CI green, then release artifacts. Do not publish private lab credentials, local evidence or local database files.

## Preflight

From the repository root:

```powershell
git status --short
python -m pytest
Push-Location frontend; npm run build; Pop-Location
docker build --build-arg VITE_API_BASE="" -t cluster-assurance-orchestrator:local .
```

Check that ignored private files are not staged:

- `config/local.env`
- `config/appliance.env`
- `evidence/`
- `.venv/`
- `frontend/node_modules/`
- appliance ZIPs that contain environment-specific images unless intentionally attached to a release

## First Publication

If the target GitHub repository already exists:

```powershell
git init
git branch -M main
git add .
git commit -m "Initial Cluster Assurance Orchestrator publication"
git remote add origin https://github.com/<owner>/<repo>.git
git push -u origin main
```

If the remote contains existing commits, fetch and inspect it before pushing:

```powershell
git fetch origin
git log --oneline --decorate --graph --all -20
```

Do not overwrite unrelated remote history.

## Ongoing Changes

Use branch-oriented publication:

```powershell
git switch -c codex/docker-appliance-publication
git add .
git commit -m "Add Docker and appliance packaging"
git push -u origin codex/docker-appliance-publication
```

Open a pull request, wait for GitHub CI, then merge into `main`.

## Appliance Release

After CI is green on the release commit:

```powershell
.\scripts\build-appliance.ps1 -Version 0.1.0
```

Attach these to a GitHub Release:

- `dist-appliance/cluster-assurance-orchestrator-0.1.0-appliance.zip`
- `dist-appliance/cluster-assurance-orchestrator-0.1.0-appliance.zip.sha256`

State the support boundary clearly:

- independent project, not affiliated with or supported by Nutanix
- read-only Prism collection by default
- lab TLS evidence is not production approval evidence
- NCC is planning-only; SSH execution is disabled
