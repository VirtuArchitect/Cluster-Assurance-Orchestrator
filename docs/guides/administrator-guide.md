# Administrator and Data Protection Guide

Configure access, persistence, backups and evidence sharing with explicit limitations.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Access and secrets

1. Use unique local accounts and the least-privilege role that supports the test. Viewers inspect saved evidence; operators need the relevant read-only collection permission. Administrative controls remain separately restricted.

2. Validate effective permissions with positive and negative tests using designated test accounts. A configured role matrix is not access-control certification. Review session expiry and sign-out behavior as part of acceptance.

3. Keep credential changes in approved secret handling. Do not paste passwords into tickets or public examples. Preserve the authentication secret with protected backups where required for restoration; losing key material can prevent saved secret recovery.

## 2. Persistence and backups

1. Docker/appliance deployments use PostgreSQL for administration and named volumes for persistent evidence. SQLite fallback is for local development; confirm the active backend before relying on persistence.

2. Use Settings > Storage for admin-only database backup creation/download. Protect exports as sensitive. Capture the application version, database version, backup time and checksums with the test record.

3. A database export does not include every evidence file, deployment setting or external secret. Back up the documented volumes and configuration separately. Do not publish raw backups or runtime evidence.

## 3. Retention and restoration

1. Review configured audit, execution and evidence retention plus minimum retained runs. Retention settings are policy inputs, not proof of backup coverage or regulatory compliance.

2. Exercise restoration in a separate environment before any cutover. Verify sign-in, roles, connections, evidence integrity and historical incidents without contacting production targets unintentionally.

3. Keep the old image and pre-change data/configuration snapshots. A simple image rollback may be unsafe after schema/data changes. Restore a compatible snapshot under a reviewed procedure rather than overwriting current volumes.

## 4. Evidence sharing and escalation

1. Operational outputs may expose hostnames, addresses, UUIDs, user names, task text and topology even when passwords are hidden. Review the full export including metadata, filenames, links and embedded images.

2. Use synthetic documentation data or replace identifying values consistently with reserved example names and documentation IP addresses. Do not use blurring as the sole protection for sensitive screenshots.

3. Keep internal incident evidence under approved access controls. For vendor escalation, share the minimum required through an approved secure channel; retain an internal mapping only where policy permits.

Source basis: backend/app/services/admin_store.py, backend/app/services/storage_ops.py, backend/app/api/routes.py, docs/appliance.md
