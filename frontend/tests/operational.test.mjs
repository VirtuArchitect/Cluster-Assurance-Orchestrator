import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";

const source = readFileSync(new URL("../src/operational.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
const { collectionEvidenceConfidence, connectionTestPosture, sourceTrafficLight, operatorQueue, formatEvidenceAge, incompleteRecoveries, monitoringPosture, hasCollectionPermission, ageSeconds, groupAuthenticationFailures, groupedFindingObservations, collectionStatus, inventoryHealthStatus } = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
const collector = (domain, code = 401, alias = "pc") => ({ source: "prism_central", endpoint_alias: alias, domain, status_code: code, status: code === 200 ? "HEALTHY" : "UNKNOWN" });

test("authentication failures group by endpoint and code; raw results stay intact", () => {
  const raw = [collector("inventory"), collector("storage"), collector("network", 403), collector("hardware", 401, "other"), collector("capacity", 200)];
  const grouped = groupAuthenticationFailures(raw);
  assert.equal(grouped.length, 4);
  assert.match(grouped[0].summary, /2 affected collector/);
  assert.match(grouped[1].summary, /Access forbidden/);
  assert.equal(raw[0].summary, undefined);
  assert.equal(raw.length, 5);
});

test("missing, stale and successful collection cannot imply infrastructure health", () => {
  assert.equal(collectionStatus(null), "UNKNOWN");
  assert.equal(collectionStatus({ collectors: [], generated_at: new Date().toISOString() }), "UNKNOWN");
  const run = { collectors: [collector("inventory", 200)], generated_at: new Date().toISOString() };
  assert.equal(collectionStatus(run), "HEALTHY");
  assert.equal(inventoryHealthStatus(run), "UNKNOWN");
  assert.equal(collectionStatus({ ...run, generated_at: "2020-01-01T00:00:00Z" }), "OVERDUE");
  assert.equal(collectionStatus({ ...run, generated_at: "invalid" }), "OVERDUE");
  assert.equal(collectionStatus({ ...run, collectors: [collector("inventory")] }), "UNKNOWN");
});

test("findings count one authentication incident without dropping unrelated findings", () => {
  const collectors = ["inventory", "storage", "hardware", "network", "capacity"].map((domain) => ({ ...collector(domain), summary: `${domain} HTTP 401` }));
  const observations = collectors.map((c) => ({ source: c.source, summary: c.summary, status: "UNKNOWN" }));
  observations.push({ source: "prism_element", summary: "storage HTTP 404", status: "UNKNOWN" });
  const grouped = groupedFindingObservations({ collectors, observations });
  assert.equal(grouped.length, 2);
  assert.equal(grouped[0].check_id, "AUTHENTICATION");
  assert.match(grouped[0].summary, /5 affected collector/);
  assert.equal(grouped[1].source, "prism_element");
  assert.equal(observations.length, 6);
});

test("freshness advances from the timestamp and missing/future evidence stays unknown", () => {
  const collected = "2026-10-17T13:40:44Z";
  assert.equal(ageSeconds(collected, Date.parse("2026-10-17T13:48:44Z")), 480);
  assert.equal(ageSeconds(collected, Date.parse("2026-10-17T13:49:44Z")), 540);
  assert.equal(ageSeconds("invalid"), null);
  assert.equal(ageSeconds(null), null);
  assert.equal(ageSeconds("2999-01-01T00:00:00Z"), null);
});

test("older login profiles without permissions are safe and never grant collection access", () => {
  assert.equal(hasCollectionPermission(null), false);
  assert.equal(hasCollectionPermission({ role_id: "admin" }), false);
  assert.equal(hasCollectionPermission({ permissions: ["view_evidence"] }), false);
  assert.equal(hasCollectionPermission({ permissions: ["run_read_only_inventory"] }), true);
  assert.equal(hasCollectionPermission({ permissions: ["all_permissions"] }), true);
});

const now = Date.parse("2026-10-18T10:00:00Z");
const feed = (source, kind) => ({ source, kind, complete: true, status: "COLLECTED" });
const report = () => ({ available: true, generated_at: new Date(now - 30_000).toISOString(), collectors: ["prism-central", "prism-element"].flatMap(source => ["alerts", "events"].map(kind => feed(source, kind))), incidents: [] });
const incident = (source, severity, extra = {}) => ({ source, severity, availability: "CURRENT", resolved: false, last_occurrence_at: "2026-10-18T09:00:00Z", ...extra });

test("operator posture keeps PE and PC separate and critical alerts first", () => {
  const data = report();
  data.incidents = [incident("prism-element", "WARNING"), incident("prism-central", "CRITICAL"), incident("prism-element", "INFO"), incident("prism-element", "CRITICAL", { resolved: true })];
  const pc = monitoringPosture(data, "prism-central", now);
  const pe = monitoringPosture(data, "prism-element", now);
  assert.equal(pc.label, "Critical alerts reported");
  assert.equal(pc.critical, 1);
  assert.equal(pe.label, "Warnings reported");
  assert.equal(pe.critical, 0);
  assert.equal(monitoringPosture(data, undefined, now).incidents[0].severity, "CRITICAL");
});

test("stale, absent, future and incomplete monitoring never declares current status", () => {
  assert.equal(monitoringPosture(null, undefined, now).verified, false);
  for (const generated_at of ["2020-01-01T00:00:00Z", "invalid", new Date(now + 120_000).toISOString()]) {
    const state = monitoringPosture({ ...report(), generated_at }, undefined, now);
    assert.equal(state.label, "Current status unknown");
  }
  const data = report();
  data.collectors[0].complete = false;
  assert.equal(monitoringPosture(data, "prism-central", now).verified, false);
  assert.equal(monitoringPosture(data, "prism-element", now).verified, true);
  assert.equal(monitoringPosture(data, undefined, now).verified, false);
});

test("no alerts and unknown severities remain explicit rather than proving health", () => {
  const data = report();
  assert.equal(monitoringPosture(data, undefined, now).label, "No critical or warning alerts");
  data.incidents = [incident("prism-central", "UNKNOWN")];
  assert.equal(monitoringPosture(data, undefined, now).label, "Review unclassified alerts");
  data.incidents[0].availability = "UNAVAILABLE";
  assert.equal(monitoringPosture(data, undefined, now).incidents.length, 0);
});


test("recovery actions select latest observation without changing resolved alert counts", () => {
  const data = report();
  const recovery = incident("prism-central", "CRITICAL", { id: "latest", source_key: "pc", cluster_id: "cluster", check_id: "200335", resolved: true, triage: { category: "Prism Central microservices infrastructure" }, deployment_diagnostics: { status: "BLOCKED", observed_at: data.generated_at } });
  data.incidents = [{ ...recovery, id: "older", last_occurrence_at: "2026-10-17T09:00:00Z" }, recovery];
  assert.equal(incompleteRecoveries(data, now).length, 1);
  assert.equal(incompleteRecoveries(data, now)[0].incident.id, "latest");
  assert.equal(incompleteRecoveries(data, now)[0].confirmed, true);
  assert.equal(monitoringPosture(data, undefined, now).critical, 0);
  for (const observed_at of ["invalid", "2020-01-01", "2999-01-01"]) {
    data.incidents = [{ ...recovery, deployment_diagnostics: { status: "BLOCKED", observed_at } }];
    assert.equal(incompleteRecoveries(data, now)[0].confirmed, false);
  }
  data.incidents = [recovery]; data.collectors[0].complete = false;
  assert.equal(incompleteRecoveries(data, now)[0].confirmed, false);
  data.incidents = [recovery, { ...recovery, last_occurrence_at: "2026-10-18T09:30:00Z", deployment_diagnostics: { status: "NO_CONFIRMED_BLOCKER" } }];
  assert.equal(incompleteRecoveries(data, now).length, 0);
});


test("operator queue merges alert and recovery action, preserves resolved recovery and source freshness", () => {
  const data = report();
  const pc = incident("prism-central", "CRITICAL", { id: "pc", source_key: "pc", cluster_id: "c", check_id: "200335", triage: { category: "Prism Central microservices infrastructure" }, deployment_diagnostics: { status: "BLOCKED", observed_at: data.generated_at } });
  const pe = incident("prism-element", "WARNING", { id: "pe" });
  data.incidents = [pc, pe];
  assert.equal(operatorQueue(data, now).length, 2);
  assert.equal(operatorQueue(data, now)[0].recovery, true);
  assert.equal(operatorQueue(data, now)[0].confirmed, true);
  pc.resolved = true;
  assert.equal(operatorQueue(data, now).length, 2);
  assert.equal(monitoringPosture(data, undefined, now).critical, 0);
  data.collectors[0].complete = false;
  assert.equal(operatorQueue(data, now)[0].confirmed, false);
  assert.equal(operatorQueue(data, now)[1].confirmed, true);
  assert.equal(operatorQueue({ ...data, generated_at: "2020-01-01" }, now).every(row => !row.confirmed), true);
  assert.equal(operatorQueue(null, now).length, 0);
  assert.equal(formatEvidenceAge(740 * 3600), "30d ago");
  assert.equal(formatEvidenceAge(null), "Time unknown");
});


test("missing microservices diagnostics remain a recovery follow-up, never a confirmed blocker", () => {
  const data = report();
  data.incidents = [incident("prism-central", "CRITICAL", { id: "pc", triage: { category: "Prism Central microservices infrastructure" } })];
  const [row] = operatorQueue(data, now);
  assert.equal(row.recovery, true);
  assert.equal(row.confirmed, false);
  data.incidents[0].resolved = true;
  assert.equal(operatorQueue(data, now).length, 0);
});


test("traffic light counts sources rather than alerts and requires fresh complete evidence", () => {
  const data = report();
  const counts = report => Object.fromEntries(sourceTrafficLight(report, now).map(segment => [segment.key, segment.count]));
  assert.deepEqual(counts(null), { critical: 0, warning: 0, clear: 0, unknown: 2 });
  assert.equal(counts(data).clear, 2);
  data.incidents = [incident("prism-central", "CRITICAL"), incident("prism-central", "CRITICAL"), incident("prism-element", "WARNING")];
  assert.deepEqual(counts(data), { critical: 1, warning: 1, clear: 0, unknown: 0 });
  data.collectors[0].complete = false;
  assert.deepEqual(counts(data), { critical: 0, warning: 1, clear: 0, unknown: 1 });
  assert.equal(counts({ ...data, generated_at: "2020-01-01" }).unknown, 2);
  assert.equal(counts({ ...data, generated_at: "2999-01-01" }).unknown, 2);
  data.incidents = [incident("prism-element", "UNKNOWN")];
  assert.equal(counts(data).unknown, 2);
});


test("inventory confidence cannot pass missing age, stale evidence, failed collectors or TLS bypass", () => {
  const base = { available: true, demo: false, failureCount: 0, age: 10, tls: "strict" };
  assert.equal(collectionEvidenceConfidence(base).status, "HEALTHY");
  for (const age of [null, -1, NaN, Infinity]) assert.equal(collectionEvidenceConfidence({ ...base, age }).status, "UNKNOWN");
  for (const extra of [{ age: 86400 }, { tls: "insecure_skip_verify" }, { failureCount: 1 }]) assert.equal(collectionEvidenceConfidence({ ...base, ...extra }).status, "WARNING");
  assert.equal(collectionEvidenceConfidence({ ...base, available: false }).status, "UNKNOWN");
  assert.equal(collectionEvidenceConfidence({ ...base, demo: true }).status, "UNKNOWN");
  assert.match(collectionEvidenceConfidence(base).detail, /health.*unverified/);
});

test("one passed connection test cannot make a partial connection set pass", () => {
  assert.equal(connectionTestPosture([]), "UNKNOWN");
  assert.equal(connectionTestPosture(["READY", "READY"]), "HEALTHY");
  assert.equal(connectionTestPosture(["READY", "UNREACHABLE"]), "WARNING");
  assert.equal(connectionTestPosture(["READY", "AUTH_FAILED"]), "WARNING");
});
