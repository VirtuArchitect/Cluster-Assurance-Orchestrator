# Prism monitoring and incident triage

The Prism Incidents view collects native alerts and events through authenticated,
read-only `GET /PrismGateway/services/rest/v2.0/{alerts|events}/` requests. Both
development endpoints were probed before implementation. API availability on other
versions is not implied. No SDK or runtime dependency was added.

## Operator workflow

1. Open **Prism Incidents** and select **Collect alerts and events**. Operators need
   `run_read_only_inventory`; viewers can inspect saved evidence with `view_evidence`.
2. Check all four source/feed rows. Incomplete pagination, malformed records, HTTP
   errors and unsupported routes produce UNKNOWN coverage, never a clear-health result.
3. Filter by lifecycle, severity, source or affected entity. Open an incident to inspect
   the original ID, check, affected entities, source timestamps, observation timestamps,
   acknowledgement, resolution, history and raw-response SHA-256 references.
4. Follow the curated symptom-based investigation steps. They include expected
   outcomes, failure branches, escalation and recovery criteria. Guidance is not a
   confirmed root cause. Vendor possible causes remain separately labelled. Verify
   guidance and KB applicability against installed AOS, PC and NCC versions.
5. Related events share an affected entity and fall within one hour of the source alert
   occurrence. This is contextual correlation, not proof of causation.

Optional automatic collection runs every 60 seconds **only while this view is open**.
With automatic collection off, the view refreshes saved evidence every 30 seconds;
this does not contact Prism. Ages advance every 15 seconds and monitoring snapshots
older than two minutes are labelled stale. These are application defaults, not
universal Nutanix polling requirements. There is no unattended monitoring worker.

## Evidence and incident lifecycle

Each collection writes a uniquely named `monitoring-run-*.json` snapshot and hashed
raw page artifacts under the existing evidence volume. Snapshots are written atomically.
Paging is bounded to 20 pages of 100 records per feed; duplicate IDs, changing totals,
missing records or cap exhaustion prevent a complete-coverage claim. Collection is
serialized within the single API process; multi-worker collection coordination is not
implemented. Collection snapshot/retention policies must be reviewed before running
continuous production monitoring; no automatic deletion of monitoring evidence is added.

PE and PC observations retain their source identity; counts are explicitly source
observations rather than deduplicated infrastructure incidents. Changing an endpoint
does not inherit the previous endpoint's incident identity. Source acknowledgement and
resolution are distinct. Missing alerts become NOT_OBSERVED; failed or removed sources
retain previous incidents as UNAVAILABLE. Neither absence nor event collection closes
an incident. The last observation timestamp and evidence are preserved. Transition
history is bounded to the most recent 100 changes per incident; prior snapshots remain.

No source alert is acknowledged or resolved, and no reboot, deletion, service restart,
SSH or NCC execution is performed. Workload impact and recovery validation are explicitly
unverified. TLS bypass remains visible and disqualifies evidence from production approval.

## Interfaces

- `GET /api/v1/monitoring/latest`: saved report, or an explicit unavailable state.
- `POST /api/v1/monitoring/collect`: operator-authorized read-only source collection,
  with a local audit record. Concurrent collection returns HTTP 409.
- `GET /api/v1/monitoring/incidents/{id}`: authenticated incident detail and collection provenance.

## References

- [Prism v2 API reference](https://www.nutanix.dev/api_reference/apis/prism_v2.html)
- [Nutanix support portal](https://portal.nutanix.com/)
- [Nutanix Support Guide](https://www.nutanix.com/content/dam/nutanix/resources/support/nutanix-support-guide.pdf)
