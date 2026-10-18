import type { Collector, InventoryRun, HealthStatus, Observation } from "./main";
import type { MonitoringReport } from "./monitoring";

export function monitoringPosture(report: MonitoringReport | null, source?: string, now = Date.now()) {
  const feeds = (report?.collectors ?? []).filter((feed) => !source || feed.source === source);
  const age = ageSeconds(report?.generated_at, now);
  const fresh = !!report?.available && age != null && age <= 120;
  const complete = (source ? [source] : ["prism-central", "prism-element"]).every((name) =>
    ["alerts", "events"].every((kind) => feeds.some((feed) => feed.source === name && feed.kind === kind && feed.complete && feed.status === "COLLECTED")));
  const open = (report?.incidents ?? []).filter((incident) => (!source || incident.source === source) && incident.availability === "CURRENT" && !incident.resolved);
  const rank = (severity: string) => ({ CRITICAL: 0, WARNING: 1, UNKNOWN: 2, INFO: 3 }[severity] ?? 2);
  const incidents = [...open].sort((a, b) => rank(a.severity) - rank(b.severity) || (Date.parse(b.last_occurrence_at ?? "") || 0) - (Date.parse(a.last_occurrence_at ?? "") || 0));
  const critical = open.filter((incident) => incident.severity === "CRITICAL").length;
  const warning = open.filter((incident) => incident.severity === "WARNING").length;
  const unknown = open.some((incident) => !["CRITICAL", "WARNING", "INFO"].includes(incident.severity));
  const verified = fresh && complete;
  const label = !verified ? "Current status unknown" : critical ? "Critical alerts reported" : warning ? "Warnings reported" : unknown ? "Review unclassified alerts" : "No critical or warning alerts";
  const tone = !verified ? "unknown" : critical ? "critical" : warning ? "warning" : unknown ? "unknown" : "clear";
  return { feeds, age, fresh, complete, verified, incidents, critical, warning, label, tone };
}

export function hasCollectionPermission(user: { permissions?: string[] } | null): boolean {
  return user?.permissions?.some((permission) => ["all_permissions", "run_read_only_inventory"].includes(permission)) ?? false;
}

export function ageSeconds(timestamp: string | null | undefined, now = Date.now()): number | null {
  const value = Date.parse(timestamp ?? "");
  if (!Number.isFinite(value) || value > now + 60_000) return null;
  return Math.max(0, Math.floor((now - value) / 1000));
}

export function runIsStale(run: InventoryRun | null) {
  const age = ageSeconds(run?.generated_at);
  return age == null || age >= 24 * 60 * 60;
}

export function collectionStatus(run: InventoryRun | null): HealthStatus {
  if (!run?.collectors.length) return "UNKNOWN";
  if (runIsStale(run)) return "OVERDUE";
  return domainStatus(run.collectors, "UNKNOWN");
}

export function inventoryHealthStatus(_run: InventoryRun | null): HealthStatus {
  // These collectors capture inventory; no infrastructure health rules run here.
  return "UNKNOWN";
}

export function groupAuthenticationFailures(collectors: Collector[]): Collector[] {
  const groups = new Map<string, Collector[]>();
  const other: Collector[] = [];
  for (const collector of collectors) {
    if (collector.status_code !== 401 && collector.status_code !== 403) {
      other.push(collector);
      continue;
    }
    const key = `${collector.source}:${collector.endpoint_alias}:${collector.status_code}`;
    groups.set(key, [...(groups.get(key) ?? []), collector]);
  }
  return [...groups.values()].map((items) => ({
    ...items[0],
    status: "UNKNOWN" as HealthStatus,
    summary: `${items[0].status_code === 401 ? "Authentication rejected" : "Access forbidden"}: ${items.length} affected collector(s) (${items.map((item) => item.domain ?? "inventory").join(", ")}). Review stored credentials${items[0].status_code === 403 ? " and permissions" : ""}, test the connection, then rerun collection.`
  })).concat(other);
}

export function groupedFindingObservations(run: InventoryRun | null): Observation[] {
  const auth = (run?.collectors ?? []).filter((collector) => collector.status_code === 401 || collector.status_code === 403);
  const observations = (run?.observations ?? []).filter((observation) => !auth.some((collector) =>
    collector.source === observation.source && collector.summary === observation.summary));
  return groupAuthenticationFailures(auth).map((collector) => ({
    check_id: collector.status_code === 401 ? "AUTHENTICATION" : "AUTHORIZATION",
    status: "UNKNOWN" as HealthStatus,
    source: collector.source,
    summary: collector.summary,
    evidence_ref: collector.raw_artifact?.uri ?? null
  })).concat(observations);
}


export function domainStatus(collectors: Collector[], fallback: HealthStatus): HealthStatus {
  if (!collectors.length) {
    return fallback;
  }
  const statuses = collectors.map((collector) => collector.status);
  if (statuses.includes("CRITICAL")) {
    return "CRITICAL";
  }
  if (statuses.includes("UNKNOWN")) {
    return "UNKNOWN";
  }
  if (statuses.includes("WARNING") || statuses.includes("OVERDUE")) {
    return "WARNING";
  }
  return "HEALTHY";
}
