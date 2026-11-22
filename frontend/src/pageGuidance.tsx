import React from "react";
import { ageSeconds, formatEvidenceAge } from "./operational";

const guidance: Record<string, { scope: string; limit: string; next: string; basis: "inventory" | "monitoring" | "configuration" }> = {
  triage: { scope: "Priorities from Prism alerts and saved collection results.", limit: "Source severity is not independently verified service impact.", next: "Refresh monitoring, identify the affected service and open its incident runbook.", basis: "monitoring" },
  estate: { scope: "Saved entity identities, versions and source availability.", limit: "PE and PC can describe the same cluster. Inventory is not a health assessment.", next: "Confirm the source and collection time before using an entry in triage.", basis: "inventory" },
  runs: { scope: "Read-only inventory probes, response results and artifacts.", limit: "Successful collection does not establish infrastructure health.", next: "Review failed probes and evidence age; recollect after correcting access.", basis: "inventory" },
  incidents: { scope: "Prism alert observations, events and targeted deployment checks.", limit: "Acknowledgement and resolution do not establish recovery or root cause.", next: "Confirm current source visibility, assess impact and follow the incident's validation steps.", basis: "monitoring" },
  findings: { scope: "Collection problems grouped by endpoint and failure type.", limit: "An API or authentication failure is a monitoring gap, not proof of a cluster fault.", next: "Inspect HTTP/error evidence, restore read-only access and repeat collection.", basis: "inventory" },
  schedules: { scope: "Configured schedules, target previews and recorded executions.", limit: "A ready preview is not an executed run or proof of an unattended scheduler.", next: "Check target mapping, timezone and the latest completed run after the due time.", basis: "configuration" },
  evidence: { scope: "Saved collection artifacts, hashes, retention and trust metadata.", limit: "A recorded hash or retained archive does not prove recovery or production approval.", next: "Check age, completeness and TLS separately; validate archives with a restore drill when required.", basis: "inventory" },
  settings: { scope: "Stored configuration, account setup and latest connection-test results.", limit: "Configured accounts or a passed test do not prove current collection or effective access.", next: "Review failed tests and readiness evidence; validate permissions and recollect after approved changes.", basis: "configuration" }
};

export function PageGuidance({ page, inventoryAt, monitoringAt }: { page: string; inventoryAt?: string | null; monitoringAt?: string | null }) {
  const item = guidance[page];
  if (!item) return null;
  const timestamp = item.basis === "monitoring" ? monitoringAt : inventoryAt;
  return <section className="page-guidance" aria-label="Operator interpretation guide">
    <div><strong>What this page tells you</strong><p>{item.scope}</p><small>{item.basis === "configuration" ? "Configuration and saved results; not continuous validation." : `${item.basis === "inventory" ? "Inventory" : "Monitoring"} evidence: ${formatEvidenceAge(ageSeconds(timestamp))}${timestamp ? ` · ${new Date(timestamp).toLocaleString()}` : " · no collection timestamp"}`}</small></div>
    <div><strong>What it does not prove</strong><p>{item.limit}</p></div>
    <div><strong>Operator next step</strong><p>{item.next}</p></div>
  </section>;
}
