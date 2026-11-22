# Tutorial Workbook: Six Guided Exercises

Practice the console workflow using explicitly synthetic scenarios.

Version: 0.2.0-rc.1. All examples are synthetic.

## 1. Orientation and status interpretation

1. Open the public demo from the project site. It is static and cannot contact Prism or persist real appliance settings. All examples in this workbook are fictional; example.invalid hosts and 192.0.2.0/24 addresses are documentation-only.

2. Exercise 1: compare PE and PC source cards, totals and evidence confidence. Explain why a green source segment cannot certify cluster health. Expected result: the operator can distinguish source count from alert count.

3. Exercise 2: inspect stale evidence in Operator Triage and Health Runs. Expected result: the operator requests a fresh collection rather than declaring the estate healthy from saved COLLECTED responses.

## 2. Collection failure and incident investigation

1. Exercise 3: consider a synthetic HTTP 401 on pc.example.invalid. Find the collection diagnostics interpretation guide and identify grouped authentication failures. Expected next step: validate the account through approved administration, then recollect; do not report a cluster outage solely from 401.

2. Exercise 4: follow a fictional A200335 incident. Compare a failed CMSP precheck to unset matched PE prerequisites. Expected result: describe a likely contributor and remaining unknowns without claiming runtime root cause.

3. Explain why restoring task-list API access alone does not establish deployment recovery. List independent service checks and affected PC functions that the responsible administrator must validate.

## 3. Recovery follow-up and recurrence

1. Exercise 5: the synthetic source alert is manually resolved while deployment remains blocked. Expected result: retain the recovery follow-up and list prerequisites, supported correction planning and post-change validation.

2. A new source occurrence appears later. Compare lifecycle history, resolution actor/type and deployment evidence. Expected result: identify recurrence without counting the old resolved record as a current open alert.

3. Do not click infrastructure change controls in vendor products during this tutorial. The app collects evidence and recommends triage; corrective action follows a separate authorised change process.

## 4. Evidence handover

1. Exercise 6: prepare an anonymised handover with version/revision, evidence age, source/feed completeness, original check type, synthetic affected entity, observations and next action.

2. Review Evidence and Settings > About. State why a recorded hash is not a restore test and why a dirty build cannot be accepted as an immutable release. Expected result: a test lead can reproduce which build was assessed.

3. Before sharing, remove names, credentials, private addresses, real UUIDs, account names and internal paths from the entire deliverable. Use the workbook as the safe source; do not export lab records into the public site.

Source basis: frontend/src/main.tsx, frontend/src/operatorDashboard.tsx, frontend/src/monitoring.tsx
