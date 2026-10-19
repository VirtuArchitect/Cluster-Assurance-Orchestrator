# Prism monitoring and incident triage

The Prism Incidents view collects native alerts and events through authenticated,
read-only `GET /PrismGateway/services/rest/v2.0/{alerts|events}/` requests. Both
development endpoints were probed before implementation. API availability on other
versions is not implied. No SDK or runtime dependency was added.

## Operator workflow

The dashboard starts with an operations watch, separate **PE cluster operations**
and **PC management plane** cards, and up to five prioritized open alert observations.
Critical alerts precede warnings; each action opens its exact incident. Source cards
open the queue filtered to PE or PC. Counts remain source observations, not deduplicated
faults. Inventory success and administration/readiness are shown separately.

Use **Refresh PE & PC monitoring** to collect alerts and events directly from the
dashboard. Current alert posture requires evidence no older than two minutes and
complete alerts and events feeds for the relevant source. Missing, incomplete or stale
evidence displays **Current status unknown**, with saved priorities retained. Even
**No critical or warning alerts** is an alert result, not proof of complete cluster health.
Dashboard auto-refresh is optional, every 60 seconds, and stops when the dashboard closes.

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

Optional automatic collection runs every 60 seconds **only while the selected dashboard or incident view is open**.
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

## CVM /home filesystem alerts

CVM/Controller VM space or inode alerts naming `/home` (including its subdirectories)
receive filesystem-specific triage before generic capacity/hardware matching. Both
PE and PC source observations retain their identities. PCVM alerts and storage
container capacity alerts do not inherit this CVM-specific runbook.

The guidance asks an authorized administrator to record `df -h /home` and
`df -i /home`, investigate scoped directory growth, compare filesystem and directory
totals, and involve support for open-but-deleted files or unclear cleanup ownership.
Commands are operator guidance only; collection continues to use Prism APIs with
SSH and NCC execution disabled. No fixed universal usage threshold, deletion command,
CVM disk expansion or automatic restart is prescribed. Recovery requires stable byte
and inode headroom, targeted check results, a source-resolved alert and service validation.

Use the original alert's KB and installed-release documentation to approve cleanup.
Nutanix's support catalogue identifies [KB 1540](https://portal.nutanix.com/kb/1540)
for CVM `/home` fullness and [KB 1532](https://portal.nutanix.com/kb/1532) for inode
checks (portal access required). The UI continues to link only KB IDs supplied by the
source alert; it does not inject these references into unrelated incidents.

## PC microservices infrastructure (A200335)

PC alerts with the native check ID 200335/A200335 or the specific "Microservices
Infrastructure is not in healthy state" message receive a dedicated runbook. It
separates PC management-plane impact from PE/workload state, then checks deployment
and upgrade tasks, resources, dependencies and version-supported component diagnostics.
All diagnostic commands remain operator/support guidance; the console executes none.
Recovery includes independent microservices health and affected PC function checks.

A separately labelled curated reference links [KB 20379](https://portal.nutanix.com/kb/20379),
listed in [Nutanix's published KB catalogue](https://next.nutanix.com/how-it-works-22/new-kb-articles-published-on-week-ending-november-29-2025-45075).
The catalogue identifies a false-positive case for A200335; affected-version details
and remediation require authenticated portal review. The console does not infer
applicability, downgrade severity, suppress the alert or resolve it. Curated links
are separate from KB IDs supplied by the source alert.

## Observed A200335 deployment blockers

For a current, unresolved PC microservices incident, monitoring additionally reads
`POST /api/nutanix/v3/tasks/list` (read-list only, 100 records/page, maximum 20 pages)
and `GET /PrismGateway/services/rest/v2.0/cluster/` on the configured PE. These are
not deployment, precheck execution or configuration requests. Task totals and IDs
must be consistent; malformed, capped, unauthorized or incomplete responses are UNKNOWN.
Alert feed coverage and targeted diagnostic coverage are reported separately.

The incident selects the newest deployment, links its precheck by parent UUID or
identical creation timestamp, and checks that its error identifies the configured PE
hostname before confirming a prerequisite blocker. A newer successful deployment,
a different PE, missing fields or unrelated historical prechecks cannot establish a
current blocker. The UI reports the parent task and child status separately, including
RUNNING parent / FAILED precheck. Task correlation does not establish alert causality.

Only explicit null/empty VIP and Data Services IP fields are reported as unset.
The API does not independently establish FQDN configuration; that remains labelled
unverified. Blockers, next actions, observation time, run ID and hashed raw task/PE
responses are saved with the monitoring snapshot. A confirmed blocker becomes the
first dashboard triage check. Old snapshots are not rewritten and resolved/unsupported
observations do not automatically trigger these additional requests.

Failed fresh diagnostics display UNKNOWN, never a retained blocker as current or a
cleared prerequisite. No address allocation, DNS, task retry/cancellation, precheck
execution, reboot, SSH or NCC execution occurs. Use an approved change and supported
recovery process before retrying a blocked deployment.

## Informational A200335 remediation plan

Microservices incidents include a UI-only remediation plan for PE network prerequisites.
It requires fresh evidence, address/DNS approval, dependency and access checks, then
staged VIP, optional FQDN, Data Services IP and supported deployment-recovery validation.
Rollback distinguishes changes made before consumers depend on the addresses from
recovery after CMSP or other services use them. Address placeholders are never filled
with guessed lab values. The reference guide must be matched to the installed release.

The plan is also visible on retained/resolved incidents as guidance; it does not imply
a current blocker. Disclosure controls only expand text: there are no configuration,
precheck execution, retry, cancellation or rollback actions and no operator sign-off
is recorded. Deployment diagnostic evidence remains separately timestamped and scoped.

A200335 recovery verification also collects fresh deployment and PE prerequisite evidence
for resolved current PC observations, using one shared diagnostic per collection.
Source resolution remains separate from recovery: a fresh confirmed prerequisite blocker
shows recovery incomplete; absent, failed, stale or unblocked diagnostics never establish
component health or operator recovery sign-off. Unavailable observations receive no
retained diagnostic as current.

The dashboard displays a separate A200335 recovery warning and immediate action for
confirmed prerequisite blockers, including resolved source alerts. It links to the
latest observation per source/cluster/check without inflating open-alert counts.
Stale or incomplete evidence is labeled unconfirmed and requires refresh.
