import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";

const source = readFileSync(new URL("../src/operational.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
const { hasCollectionPermission, ageSeconds, groupAuthenticationFailures, groupedFindingObservations, collectionStatus, inventoryHealthStatus } = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
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
