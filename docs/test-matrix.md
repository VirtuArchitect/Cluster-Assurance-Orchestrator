# Test Matrix

## Foundation Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Configuration | Missing Prism password | Validation refuses to start and redacts the missing value from logs |
| Configuration | Demo mode enabled | No Prism, SSH, NCC, Checkmk or ServiceNow calls are attempted |
| Secrets | Log capture with configured credentials | Passwords, cookies, tokens and authorization headers are absent |
| TLS | Strict mode with invalid lab certificate | Endpoint check fails and produces `UNKNOWN` |
| TLS | Lab insecure mode enabled | Endpoint check may proceed, but result is labelled lab-only |

## Prism API Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Reachability | Prism Central endpoint reachable | Collector records reachable status and timestamp |
| Reachability | Prism Element endpoint reachable | Collector records reachable status and timestamp |
| Authentication | Valid lab credentials | Session succeeds without logging secret material |
| Authentication | Invalid credentials | Collector produces `UNKNOWN` and audit event |
| Version discovery | Supported version response | Version and API capability are recorded |
| Version discovery | Missing or unexpected response | Capability is unsupported and status is `UNKNOWN` |
| Inventory | Cluster list response | Clusters normalize with source, external ID, name and collection time |
| Inventory | Paginated response | Collector follows documented pagination and records completeness |
| Inventory | Partial failure | Available data is shown with partial-data label |

## Health Evaluation Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Status precedence | Critical finding and unknown collector | Estate status follows documented precedence |
| Mandatory data | Mandatory collector fails | Cluster status is `UNKNOWN`, not `HEALTHY` |
| Stale data | Last successful run outside freshness window | Status is `OVERDUE` or visibly stale |
| Maintenance | Maintenance flag active | Findings remain recorded and are not converted to healthy |
| Suppression | Expired exception | Finding re-enters evaluation automatically |

## Execution Safety Tests

| Area | Test | Expected result |
| --- | --- | --- |
| NCC disabled | Attempt to run NCC in first lab phase | Request is rejected with feature-disabled response |
| SSH disabled | Attempt to provide SSH target or command | Request is rejected and audited |
| Command injection | Shell metacharacters in any operator input | Input is treated as invalid data, never command text |
| Concurrency | Two runs target the same cluster | One active run is allowed and the second is rejected or queued by policy |
| Idempotency | Duplicate scheduler tick | Exactly one run record is created |
| NCC allowlist | Browser/API submits profile identifier | Command plan is created only for an approved profile |
| NCC injection | Browser/API submits command text | Request is rejected |
| NCC parser | Unknown output format | Result is `UNKNOWN`, not healthy |
| NCC parser | FAIL or ERROR line | Result is `CRITICAL` |

## Scheduling Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Schedule preview | Daily schedule next occurrences | Occurrences are deterministic and timezone-aware |
| Schedule preview | Weekly schedule weekday | Occurrences fall on the configured weekday |
| Idempotency | Same schedule/profile/time | Same idempotency key is produced |
| Profile versioning | Profile check set changes | Definition hash changes and creates a distinct profile version reference |
| Locking | Active lock on one target | Locked target is blocked and other targets remain runnable |
| Locking | All targets locked | Occurrence is blocked and cannot start duplicate work |

## Evidence and Audit Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Evidence manifest | Completed read-only run | Manifest contains profile version, timestamps, artifact hashes and summary |
| Raw payload handling | Prism response artifact captured | Raw artifact is referenced and access-controlled, not logged |
| Audit | Endpoint configuration read/test | Actor, action, timestamp and outcome are recorded |
| Audit | Failed auth | Failure is audited without token, password or assertion data |
| Export | JSON summary export | Export matches normalized result and preserves unknown/stale states |
| Evidence manifest | Latest evidence endpoint | Manifest contains normalized inventory artifact and raw collector references |
| Integrations | Planned adapter status | Checkmk, ServiceNow, email and webhook remain disabled until configured |
| Security readiness | Lab TLS bypass | Readiness endpoint reports warning and does not imply production approval |
| RBAC readiness | Permission matrix | Viewer, operator and admin permissions are exposed for future enforcement |

## UI Smoke Tests

| Area | Test | Expected result |
| --- | --- | --- |
| Dashboard | Lab read-only result with partial data | Operator can identify what failed, where, when and why |
| Dashboard | Missing data | UI shows `UNKNOWN` or stale state, never green/healthy |
| Evidence | Run evidence page | Operator can see summary, hashes and raw artifact references |
| Navigation | Menu item selection | Each menu item renders a focused page instead of a long scrolling page |
| Suite styling | ZTF visual treatment | Console uses the shared mark, dark dashboard palette and Nutanix blue action colour |
| Accessibility | Keyboard navigation | Core dashboard and evidence workflows are keyboard-accessible |
| Branding | About page | Independence and trademark notice is visible |
