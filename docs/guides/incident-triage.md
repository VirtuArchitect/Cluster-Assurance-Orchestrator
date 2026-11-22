# Prism Incident and Recovery Runbook

Investigate A200335 recurrence and CVM filesystem pressure using evidence-specific checks.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Establish what happened

1. Open Prism Incidents and collect fresh alerts and events. Verify all four configured PE/PC alert/event feeds, pagination completeness and TLS trust. Failed collection means current state is unknown.

2. Inspect the original alert ID, check ID, lifecycle, acknowledgement, affected entities and timestamps. Correlated events are context, not causation. Distinguish source occurrence from app observation time.

3. Record source-reported possible causes separately from curated recommended triage and independently verified findings. Consult installed-release documentation and Nutanix Support before corrective infrastructure actions.

## 2. A200335: inspect deployment and prerequisites

1. For Microservices Infrastructure is not in healthy state, inspect the latest PC Microservice Infrastructure Deployment task and CMSP Prechecks child result. A RUNNING parent with a FAILED precheck is not successful deployment.

2. Read the matched PE cluster VIP and Data Services IP evidence. An empty VIP field plus a matching task error supports a prerequisite blocker; this API does not verify FQDN configuration or DNS. The app correlation is not proof of alert-to-task causality.

3. If task API access, fields or the matched PE are unavailable, retain UNKNOWN and restore read-only visibility. No matching task or no confirmed blocker does not prove runtime microservices health.

## 3. Plan correction and verify recurrence

1. Before any approved change, validate address ownership, subnet/routing, DNS, uniqueness, installed-release requirements, maintenance scope and rollback owner. Capture current configuration. Never allocate an address from this example.

2. Use supported vendor procedures under a separate change record. This app does not assign VIPs, change DNS, restart services, retry deployment, or run SSH/Kubernetes commands. If a deployment is stuck, engage Nutanix Support rather than repeatedly redeploying.

3. After correction, validate prechecks, parent deployment state, microservices/component health and affected PC functions. Recollect alerts and diagnostics. Compare recurrence to the earlier manually resolved alert; do not treat that resolution as recovery evidence.

## 4. CVM /home: inspect the correct filesystem

1. Identify the affected CVM and exact mount from the source alert. Under an approved read-only diagnostic procedure inspect df -h /home and df -i /home, mount identity and growth over time. Bytes and inodes are different failure modes.

2. Scope directory-usage inspection to the affected filesystem. Review support bundles, uploads, logs and recent upgrade activity. Recursive scans can add load. Do not treat storage data or unfamiliar files as disposable.

3. No delete, truncate or service restart is authorised by this guide. Obtain supported cleanup guidance and a separate change approval. Recheck byte/inode headroom, relevant check, source alert and service impact; escalate recurrence with time-scoped evidence.

Source basis: backend/app/services/monitoring.py, backend/app/services/pc_diagnostics.py, frontend/src/monitoring.tsx
