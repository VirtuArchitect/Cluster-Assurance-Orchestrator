import React, { useEffect, useRef, useState } from "react";
import { ageSeconds } from "./operational";

type Evidence = { method: string; path: string; http_status: number | null; artifact?: string; sha256?: string; elapsed_ms?: number; size_bytes?: number };
type Entity = { id: string; name: string; type: string };
type PrismEvent = { id: string; source_id: string; source: string; title: string; message: string; severity: string; occurred_at: string | null; affected_entities: Entity[]; evidence: Evidence };
type Incident = PrismEvent & {
  source_key: string; cluster_id: string; check_id: string; resolved: boolean; acknowledged: boolean;
  availability: string; lifecycle: string; first_seen_at: string; observed_at: string;
  last_occurrence_at: string | null; source_resolved_at: string | null; last_seen_run_id: string;
  vendor_possible_causes: unknown; vendor_details: unknown; related_events: PrismEvent[];
  vendor_description?: string; vendor_guidance?: { possible_cause: string | null; recommended_action: string | null; reported_impact: string | null };
  source_versions?: { software: string | null; ncc: string | null }; unresolved_parameters?: string[];
  history: Array<{ at: string; state: string; severity: string; run_id: string; evidence?: Evidence }>;
  triage: { category: string; basis: string; steps: Array<{ check: string; expected: string; if_failed: string }>;
    resolution_criteria: string[]; escalation: string; safety: string; kb_links: string[]; reference: string; applicability: string };
};
type Feed = { source: string; source_key: string; kind: string; status: string; complete: boolean; count: number; error: string | null; pages: Evidence[] };
export type MonitoringReport = {
  available: boolean; run_id?: string; generated_at: string | null; completed_at?: string; status?: string; tls_mode?: string;
  summary?: { critical: number; warning: number; open: number; unavailable: number };
  collectors: Feed[]; incidents: Incident[]; events: PrismEvent[];
};
const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const emptyReport: MonitoringReport = { available: false, generated_at: null, collectors: [], incidents: [], events: [] };
const date = (value?: string | null) => value ? new Date(value).toLocaleString() : "Not reported";
const age = (value?: string | null) => { const seconds = ageSeconds(value); return seconds == null ? "Unknown age" : seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`; };
const tone = (value: string) => value === "CRITICAL" ? "critical" : value === "WARNING" ? "warning" : value === "COLLECTED" ? "healthy" : "unknown";
const Badge = ({ value }: { value: string }) => <span className={`status ${tone(value)}`}>{value.replaceAll("_", " ")}</span>;

export function MonitoringSummary({ report, onOpen }: { report: MonitoringReport | null; onOpen: () => void }) {
  const stale = report?.generated_at ? (ageSeconds(report.generated_at) ?? Infinity) > 120 : true;
  return <section className="panel monitoring-summary" aria-label="Prism alert posture">
    <div><h2>Prism alert posture</h2>
      <p>{!report?.available ? "Alerts and events have not been collected. Infrastructure health remains unknown." :
        `${report.summary?.critical ?? 0} critical · ${report.summary?.warning ?? 0} warning · ${report.summary?.open ?? 0} open source observations · ${report.summary?.unavailable ?? 0} last-known incidents`}</p>
      <small>{report?.available ? `Monitoring evidence ${age(report.generated_at)} old · ${stale ? "STALE" : "recent"} · ${report.status ?? "UNKNOWN"} · ${report.tls_mode === "strict" ? "strict TLS" : "TLS unverified"}. Alert posture is not a complete health evaluation.` : "Read-only collection is available to operators."}</small>
    </div><button className="primary-button" onClick={onOpen}>Open Prism incidents</button>
  </section>;
}

export function MonitoringPage(props: { authToken: string; initial: MonitoringReport | null; onUpdate: (report: MonitoringReport) => void; canCollect: boolean; initialTarget?: { id?: string; source?: string } }) {
  const [report, setReport] = useState(props.initial ?? emptyReport);
  const [selected, setSelected] = useState<string | null>(props.initialTarget?.id ?? null);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("open");
  const [severity, setSeverity] = useState("all");
  const [source, setSource] = useState(props.initialTarget?.source ?? "all");
  const [auto, setAuto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busyRef = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { if (props.initial) setReport(props.initial); }, [props.initial]);
  async function update(collect = false) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${API}/api/v1/monitoring/${collect ? "collect" : "latest"}`, {
        method: collect ? "POST" : "GET", headers: { Authorization: `Bearer ${props.authToken}` }
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : `Monitoring request failed (HTTP ${response.status})`);
      }
      const result = await response.json() as MonitoringReport;
      if (!alive.current) return;
      setReport(result); props.onUpdate(result);
    } catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : "Monitoring is unavailable; retained evidence may be stale."); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  }
  useEffect(() => {
    void update();
    const timer = window.setInterval(() => { void update(auto && props.canCollect); }, auto ? 60_000 : 30_000);
    return () => window.clearInterval(timer);
  }, [props.authToken, auto, props.canCollect]);
  const incident = report.incidents.find((item) => item.id === selected);
  const sources = Array.from(new Set(report.collectors.map((item) => item.source)));
  const filtered = report.incidents.filter((item) =>
    (state === "all" || state === "open" && item.availability === "CURRENT" && !item.resolved || state === "resolved" && item.resolved || state === "unavailable" && item.availability !== "CURRENT") &&
    (severity === "all" || item.severity === severity) && (source === "all" || item.source === source) &&
    `${item.title} ${item.message} ${item.source_id} ${item.cluster_id} ${item.affected_entities.map((e) => e.name).join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  const failedSources = sources.filter((name) => report.collectors.some((c) => c.source === name && !c.complete));
  return <>
    <section className="panel">
      <h2>Prism alerts and events</h2>
      <p>Source alerts, diagnostic evidence and guided investigation. No Prism acknowledgement, resolution or infrastructure changes are performed.</p>
      <div className="toolbar monitoring-toolbar">
        <button className="primary-button" disabled={busy || !props.canCollect} onClick={() => void update(true)}>{busy ? "Collecting / loading…" : "Collect alerts and events"}</button>
        <button className="secondary-button" disabled={busy} onClick={() => void update()}>Refresh saved evidence</button>
        {props.canCollect ? <label><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Auto-collect every 60 seconds while this view is open</label> : <span>Viewer access: saved evidence only</span>}
      </div>
      {error ? <p role="alert" className="monitoring-warning">{error} Prior evidence is retained; this is not a clear-health result.</p> : null}
      {report.available ? <p>Last collected {date(report.generated_at)} ({age(report.generated_at)} ago) · <Badge value={report.status ?? "UNKNOWN"} /> · Run <code>{report.run_id}</code> · {report.tls_mode === "strict" ? "Strict TLS" : "TLS verification bypassed: lab evidence only"}</p> : <p>No monitoring evidence yet. Collect alerts and events to establish source coverage.</p>}
      {report.available && (ageSeconds(report.generated_at) ?? Infinity) > 120 ? <p role="status" className="monitoring-warning">Monitoring evidence is stale. No current clear-health claim can be made.</p> : null}
      <div className="monitoring-counters">
        <span>Critical open: <strong>{report.summary?.critical ?? "Unknown"}</strong></span><span>Warning open: <strong>{report.summary?.warning ?? "Unknown"}</strong></span>
        <span>Open source observations: <strong>{report.summary?.open ?? "Unknown"}</strong></span><span>Last-known incidents: <strong>{report.summary?.unavailable ?? "Unknown"}</strong></span>
      </div>
      <small>PE and PC observations retain separate source identities. Matching affected entities and events provide context; counts are not deduplicated infrastructure incidents.</small>
    </section>
    <section className="panel"><h2>Monitoring coverage and collection problems</h2>
      {failedSources.map((name) => {
        const failures = report.collectors.filter((c) => c.source === name && !c.complete);
        const http = failures.map((c) => c.pages.at(-1)?.http_status);
        const action = http.includes(401) ? "Check stored credentials, account state and authentication source; test the connection, then recollect." : http.includes(403) ? "Check the account's monitoring permissions and entity scope; do not assume the password is wrong." : http.includes(404) || http.includes(405) ? "Verify the monitoring API against the installed Prism version; do not repeatedly retry an unsupported route." : "Inspect response completeness, paging, connectivity and evidence. Prior incidents remain last-known until source visibility recovers.";
        return <article className="monitoring-warning" key={name}><strong>{name}: {failures.length} affected feed(s)</strong><p>{failures.map((c) => `${c.kind}: ${c.error}`).join(" · ")}</p><p>Recommended triage: {action}</p></article>;
      })}
      <div className="monitoring-table-wrap"><table className="monitoring-table"><thead><tr><th>Source / feed</th><th>Coverage</th><th>Records / pages</th><th>Evidence</th></tr></thead><tbody>
        {report.collectors.map((c) => <tr key={`${c.source_key}-${c.kind}`}><td>{c.source} / {c.kind}</td><td><Badge value={c.complete ? "COLLECTED" : "UNKNOWN"} /></td><td>{c.count} / {c.pages.length}</td><td><details><summary>Requests and artifact hashes</summary>{c.pages.map((p, n) => <EvidenceDetail key={n} evidence={p} />)}</details></td></tr>)}
      </tbody></table></div>
    </section>
    {incident ? <IncidentDetail incident={incident} onBack={() => setSelected(null)} /> : <section className="panel"><h2>Incident queue</h2>
      <div className="toolbar monitoring-toolbar">
        <label>Search incidents<input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Symptom, alert ID, entity or cluster" /></label>
        <label>Lifecycle<select value={state} onChange={(e) => setState(e.target.value)}><option value="open">Open in Prism</option><option value="resolved">Resolved in Prism</option><option value="unavailable">Last known / unavailable</option><option value="all">All incidents</option></select></label>
        <label>Severity<select value={severity} onChange={(e) => setSeverity(e.target.value)}><option value="all">All severities</option>{["CRITICAL", "WARNING", "INFO", "UNKNOWN"].map((v) => <option key={v}>{v}</option>)}</select></label>
        <label>Source<select value={source} onChange={(e) => setSource(e.target.value)}><option value="all">All sources</option>{sources.map((s) => <option key={s}>{s}</option>)}</select></label>
      </div><p>{filtered.length} matching source observations. Missing alerts are never automatically resolved.</p>
      <div className="monitoring-table-wrap"><table className="monitoring-table"><thead><tr><th>Severity / state</th><th>What happened</th><th>Affected entity / source</th><th>Source occurrence / observed</th></tr></thead><tbody>
        {filtered.map((item) => <tr key={item.id}><td><Badge value={item.severity} /><p>{item.availability === "CURRENT" ? item.lifecycle.replaceAll("_", " ") : item.availability.replaceAll("_", " ")}</p></td>
          <td><button className="incident-title" aria-label={`Open incident: ${item.title}`} onClick={() => setSelected(item.id)}>{item.title}</button><small>{item.triage.category}</small></td>
          <td>{item.affected_entities.map((e) => e.name).join(", ") || "Not reported"}<small>{item.source}</small></td><td>{date(item.last_occurrence_at || item.occurred_at)}<small>Observed {age(item.observed_at)} ago</small></td></tr>)}
      </tbody></table></div>{!filtered.length ? <p>No matching incidents in the saved evidence. Check source completeness and freshness before drawing conclusions.</p> : null}
    </section>}
    <section className="panel"><h2>Prism events</h2><p>Events provide investigation context. Event proximity or shared entities do not prove root cause.</p><EventTable events={report.events} /></section>
  </>;
}

function EvidenceDetail({ evidence }: { evidence: Evidence }) {
  return <dl className="incident-evidence"><dt>Read-only request</dt><dd>{evidence.method} {evidence.path}</dd><dt>HTTP / elapsed</dt><dd>{evidence.http_status ?? "No response"} / {evidence.elapsed_ms ?? "Unknown"} ms</dd><dt>Raw artifact</dt><dd>{evidence.artifact ?? "No response body"}</dd><dt>SHA-256</dt><dd><code>{evidence.sha256 ?? "Not available"}</code></dd></dl>;
}

function EventTable({ events }: { events: PrismEvent[] }) {
  return <div className="monitoring-table-wrap"><table className="monitoring-table"><thead><tr><th>Occurred / source</th><th>Event</th><th>Affected entities</th><th>Evidence</th></tr></thead><tbody>
    {events.map((e) => <tr key={e.id}><td>{date(e.occurred_at)}<small>{e.source}</small></td><td>{e.message}<small>ID {e.source_id}</small></td><td>{e.affected_entities.map((a) => a.name).join(", ") || "Not reported"}</td><td><details><summary>Request evidence</summary><EvidenceDetail evidence={e.evidence} /></details></td></tr>)}
  </tbody></table>{!events.length ? <p>No related events in the collected source window. This does not establish absence of a cause.</p> : null}</div>;
}

function IncidentDetail({ incident: i, onBack }: { incident: Incident; onBack: () => void }) {
  const detail = useRef<HTMLElement | null>(null);
  useEffect(() => { detail.current?.focus(); detail.current?.scrollIntoView({ block: "start" }); }, [i.id]);
  return <section ref={detail} tabIndex={-1} className="panel incident-detail" aria-label="Incident detail">
    <button className="secondary-button" onClick={onBack}>Back to incident queue</button>
    <h2>{i.title}</h2><p><Badge value={i.severity} /> {i.source} · {i.availability === "CURRENT" ? i.lifecycle.replaceAll("_", " ") : i.availability.replaceAll("_", " ")}</p>
    <h3>What happened</h3><p className="incident-message">{i.message}</p>
    {i.unresolved_parameters?.length ? <p>Source parameters not supplied: {i.unresolved_parameters.join(", ")}. Inspect the original Prism record before interpreting these values.</p> : null}
    {i.availability !== "CURRENT" ? <p className="monitoring-warning">Last-known observation; current source state is unverified. Absence or collection failure is not resolution.</p> : null}
    <dl className="details-grid"><div><dt>Original alert ID</dt><dd>{i.source_id}</dd></div><div><dt>Check ID</dt><dd>{i.check_id || "Not supplied"}</dd></div><div><dt>Cluster ID</dt><dd>{i.cluster_id || "Not supplied"}</dd></div>
      <div><dt>Source first occurrence</dt><dd>{date(i.occurred_at)}</dd></div><div><dt>Source last occurrence</dt><dd>{date(i.last_occurrence_at)}</dd></div><div><dt>Collected / observed</dt><dd>{date(i.observed_at)} ({age(i.observed_at)} ago)</dd></div>
      <div><dt>First seen by this app</dt><dd>{date(i.first_seen_at)}</dd></div><div><dt>Acknowledged in Prism</dt><dd>{i.acknowledged ? "Yes" : "No"} — separate from resolution</dd></div><div><dt>Resolved in Prism</dt><dd>{i.resolved ? `Yes · ${date(i.source_resolved_at)}` : "No"}</dd></div></dl>
    <h3>Affected systems and impact</h3><ul>{i.affected_entities.map((e) => <li key={`${e.type}-${e.id}`}>{e.name} · {e.type} · <code>{e.id}</code></li>)}</ul>
    <p>Business and workload impact has not been independently established. Confirm it with the affected service owner.</p>
    {i.vendor_guidance?.reported_impact ? <p>Prism-reported potential impact: {i.vendor_guidance.reported_impact}</p> : null}
    <h3>Source-reported diagnostic context</h3><p>Software version: {i.source_versions?.software ?? "Not reported"} · NCC: {i.source_versions?.ncc ?? "Not reported"}</p>
    {i.vendor_description ? <p className="incident-message">{i.vendor_description}</p> : null}
    {i.vendor_guidance?.possible_cause ? <p>Prism-reported possible cause: {i.vendor_guidance.possible_cause}</p> : null}
    {i.vendor_guidance?.recommended_action ? <p>Prism-recommended action (review before execution): {i.vendor_guidance.recommended_action}</p> : null}
    <h3>Recommended triage · {i.triage.category}</h3><p>{i.triage.basis}</p><p>{i.triage.applicability}</p>
    <ol className="triage-instructions">{i.triage.steps.map((step, n) => <li key={n}><strong>{step.check}</strong><p>Expected: {step.expected}</p><p>If not: {step.if_failed}</p></li>)}</ol>
    <details><summary>Vendor-provided possible causes and metric details</summary><pre>{JSON.stringify({ possible_causes: i.vendor_possible_causes, details: i.vendor_details }, null, 2)}</pre></details>
    <p>{i.triage.kb_links.map((link) => <a key={link} href={link} target="_blank" rel="noreferrer">Nutanix KB {link.split("/").at(-1)} </a>)}<a href={i.triage.reference} target="_blank" rel="noreferrer">Nutanix Support Portal</a></p>
    <h3>When to escalate</h3><p>{i.triage.escalation}</p><p className="monitoring-warning">{i.triage.safety}</p>
    <h3>Resolution and validation criteria</h3><ul>{i.triage.resolution_criteria.map((text) => <li key={text}>{text}</li>)}</ul><p>Prism resolution alone does not confirm workload recovery. No operator recovery validation has been recorded by this read-only view.</p>
    <h3>Incident history</h3><ol>{i.history.map((h, n) => <li key={n}>{date(h.at)} · {h.state.replaceAll("_", " ")} · {h.severity} · run <code>{h.run_id}</code>{h.evidence ? <details><summary>Transition evidence</summary><EvidenceDetail evidence={h.evidence} /></details> : null}</li>)}</ol>
    <h3>Latest supporting evidence</h3><p>Run <code>{i.last_seen_run_id}</code></p><EvidenceDetail evidence={i.evidence} />
    <h3>Related events</h3><p>Shared affected entity within one hour of the alert occurrence. Context only; no causal relationship is asserted.</p><EventTable events={i.related_events} />
  </section>;
}
