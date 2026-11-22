# Release policy

Canonical metadata lives in `backend/app/release.json`: Semantic Versioning for the UI, image/package tag and public guides; equivalent PEP 440 for Python metadata. `0.2.0-rc.1` is a controlled production-test candidate, not production approval.

- Use a new `-rc.N` for each changed candidate. Do not overwrite tags, release assets or accepted images.
- Change the canonical release and frontend package/lock versions together; run `python scripts/check-release.py` and regenerate the guides.
- Source revision and build time identify a build; a version string alone does not. UI and API identities must agree. Dirty or unknown builds are local verification only.
- New collections retain their build identity. Legacy evidence reports an unknown producer rather than being relabelled as the current release.
- Build release bundles only from clean reviewed source. The packaging script pins its Compose image and records image identity, image-tar hash and file hashes, followed by an external ZIP checksum.
- The checksum is an integrity check, not publisher authentication. Use an approved release channel and verify provenance before importing.
- No production release is created by this change. Promotion requires recorded permissions, TLS, restore, compatibility and operational acceptance tests, with an accountable approver.
- Before production acceptance, review existing floating container base tags and backend dependency ranges, vulnerability findings, TLS ingress, key storage and schema/rollback compatibility. This versioning change does not resolve those deployment controls.

## Candidate changes

The candidate includes the shared enterprise console theme and Windows-style sidebar, evidence interpretation guides, Collection Diagnostics format alignment, version/build identity, immutable packaging safeguards, and an anonymised project site with six PDF guides and six captioned video overviews and written tutorials.

## Publication boundary

The site generator reads only a curated synthetic catalogue. The Pages artifact contains `site/` plus a freshly built synthetic demo. No live collection, backup, connection export, lab screenshot or personal path is an allowed source. Automated publication scans and a human review are both required. Existing repository history and unreferenced legacy assets are not rewritten or certified anonymous by this change.
