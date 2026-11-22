# Release, Validation and Rollback Checklist

Distinguish source, package, installed runtime and acceptance evidence.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Release identity and immutability

1. The canonical version is backend/app/release.json. Candidate versions use Semantic Versioning such as 0.2.0-rc.1; Python metadata uses the equivalent 0.2.0rc1. Frontend package metadata must match the canonical semantic version.

2. Every candidate needs a new version when its contents change. Build release packages from a reviewed clean checkout and preserve full revision, UTC build time, source state, image identity and SHA-256. Never relabel or overwrite an accepted artifact.

3. A dirty or unknown source build is local verification only. A prerelease label, successful CI or a reachable UI does not constitute production approval. Record acceptance scope and accountable approver separately.

## 2. Pre-test validation

1. Run backend tests, frontend tests and production builds. Build the actual container and verify its /api/v1/health build identity against Settings > About. Record any skipped tests and unavailable dependencies.

2. Verify least-privilege access and rejection paths, strict TLS, complete PE/PC collection, stale/failed source behavior, retained history and A200335 recovery/recurrence semantics. Do not validate only the happy path.

3. Test console layout and accessibility with both themes, keyboard access and narrow screens. Verify documentation links and anonymisation scans. Public tutorial scenarios are synthetic, not hardware acceptance evidence.

## 3. Controlled cutover and rollback

1. Agree stop conditions: mismatched provenance, missing evidence, failed permissions/TLS checks, data migration uncertainty or unexpected target writes. Preserve old image and protected configuration plus verified backups.

2. Install the exact reviewed image with an explicit version/digest pin. Verify effective Compose configuration and running image identity; loading an image archive alone does not replace the running service.

3. Rollback only under the reviewed plan. Stop the affected candidate if needed, restore compatible configuration/data snapshots and start the known-good image. Validate app access and read-only mode before any recollection.

## 4. Acceptance record

1. Record version, revision, source state, image digest, package checksum, environment class, target software versions, test cases, timestamps, results, defects and residual limitations. Keep target-identifying records private.

2. Require an explicit decision: accepted for the defined test scope, rejected, or conditionally accepted with owners and expiry. No automatic production promotion is provided.

3. Release notes must distinguish implemented features, local/CI verification, lab verification and unverified production assumptions. Publish only anonymised summaries; retain detailed evidence internally.

Source basis: backend/app/release.json, backend/app/version.py, scripts/build-appliance.ps1, Dockerfile
