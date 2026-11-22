import React, { useEffect, useRef, useState } from "react";
import type { MonitoringReport } from "./monitoring";
import { SourcePostureChart } from "./sourcePostureChart";
import type { InventoryRun } from "./main";
import { monitoringPosture, ageSeconds, incompleteRecoveries, operatorQueue, formatEvidenceAge } from "./operational";
import { ArrowRight, ArrowUpRight, Clock3, Layers, RefreshCw, Search, Server, ShieldAlert, ShieldCheck } from "lucide-react";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";
const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const sources = [{ id: "prism-element", name: "Prism Element", role: "PE · Cluster operations" }, { id: "prism-central", name: "Prism Central", role: "PC · Management plane" }];
const ageLabel = formatEvidenceAge;
export function OperatorDashboard(props: {
  report: MonitoringReport | null; run: InventoryRun | null; authToken: string; canCollect: boolean;
  onUpdate: (report: MonitoringReport) => void; onOpen: (id?: string, source?: string) => void;
  onDiagnostics: () => void; onEstate: () => void; onInventory: () => void;
}) {
  const posture = monitoringPosture(props.report);
  const recoveries = incompleteRecoveries(props.report);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(!STATIC_DEMO);
  useEffect(() => {
    if (!auto || STATIC_DEMO) return;
    const timer = window.setInterval(() => void refresh(false), 30_000);
    return () => window.clearInterval(timer);
  }, [auto, props.canCollect, props.authToken]);
  async function refresh(collect = true) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null);
    try {
      const response = await fetch(`${API}/api/v1/monitoring/${collect ? "collect" : "latest"}`, { method: collect ? "POST" : "GET", headers: { Authorization: `Bearer ${props.authToken}` } });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : `Collection failed (HTTP ${response.status})`);
      }
      props.onUpdate(await response.json() as MonitoringReport);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Collection failed. Last-known evidence retained."); }
    finally { busyRef.current = false; setBusy(false); }
  }
  const queue = operatorQueue(props.report);
  const [filter, setFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [query, setQuery] = useState("");
  const visible = queue.filter(row => (filter === "all" || filter === "recovery" && row.recovery || row.incident.severity === filter)
    && (sourceFilter === "all" || row.incident.source === sourceFilter)
    && `${row.incident.title} ${row.incident.source_id} ${row.incident.check_id} ${row.incident.affected_entities.map(e => e.name).join(" ")}`.toLowerCase().includes(query.toLowerCase()));
  const inventoryIssues = (props.run?.collectors ?? []).filter(item => item.status !== "HEALTHY");
  const inventoryAge = ageSeconds(props.run?.generated_at);
  const confirmedRecoveries = recoveries.filter(item => item.confirmed).length;
  const feedCount = props.report?.collectors.filter(item => item.complete && item.status === "COLLECTED").length ?? 0;
  const states = sources.map(source => ({ ...source, state: monitoringPosture(props.report, source.id) }));
  const headline = !posture.verified ? "Current estate status unconfirmed" : posture.critical ? "Critical alerts require attention" : confirmedRecoveries ? "Recovery actions remain open" : posture.warning ? "Warnings require investigation" : posture.label;
  const observations = (props.report?.incidents ?? []).filter(item => !item.resolved);
  const metrics = [
    { label: "Critical alerts", value: posture.verified ? posture.critical : observations.filter(item => item.severity === "CRITICAL").length, tone: "critical", filter: "CRITICAL" },
    { label: "Warning alerts", value: posture.verified ? posture.warning : observations.filter(item => item.severity === "WARNING").length, tone: "warning", filter: "WARNING" },
    { label: "Open observations", value: posture.verified ? posture.incidents.length : observations.length, tone: "neutral", filter: "all" },
    { label: "Recovery follow-ups", value: queue.filter(row => row.recovery).length, tone: "warning", filter: "recovery" }
  ];
  return <div className="operator-dashboard enterprise-ops">
    <section className="ops-command" aria-label="Monitoring controls">
      <div><span className="ops-kicker">Operations overview</span><p>PE cluster operations &amp; PC management plane</p></div>
      <div className="ops-command-actions">
        <span className="ops-timestamp"><Clock3 size={14} /> {ageLabel(posture.age)}<small>Last monitoring collection</small></span>
        <label className="watch-auto"><input type="checkbox" checked={auto} disabled={STATIC_DEMO} onChange={event => setAuto(event.target.checked)} /> Refresh saved evidence / 30s</label>
        <button className="primary-button" disabled={busy || !props.canCollect} onClick={() => void refresh()}><RefreshCw size={15} className={busy ? "ops-spin" : ""} /> {busy ? "Collecting…" : "Refresh PE & PC monitoring"}</button>
      </div>
    </section>
    {error ? <div className="banner unknown" role="alert">{error} Saved evidence remains visible.</div> : null}
    <section className={`ops-verdict ops-tone-${posture.verified ? posture.tone : "unknown"}`} aria-label="Operations status">
      <div className="ops-verdict-icon"><ShieldAlert size={22} /></div>
      <div><h2>{headline}</h2><p>{posture.verified ? "Prism alert posture only. Confirm service impact and recovery in triage." : "Refresh monitoring before assessing health. Counts and issues below are saved evidence."}</p></div>
      <span className={`ops-pill ${posture.verified ? "ops-fresh" : "ops-unknown"}`}>{posture.verified ? "Current evidence" : posture.fresh ? "Incomplete coverage" : "Stale / unavailable"}</span>
    </section>
    <section className="ops-metrics" aria-label="Alert and recovery totals">
      {metrics.map(metric => <button key={metric.label} className={`ops-metric ops-tone-${metric.tone}`} onClick={() => { setFilter(metric.filter); document.getElementById("ops-priority-queue")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
        <span>{metric.label}<ArrowUpRight size={14} /></span><strong>{props.report?.available ? metric.value : "—"}</strong>
        <small>{metric.filter === "recovery" ? `${confirmedRecoveries} blockers confirmed · separate from alerts` : posture.verified ? "Current source observations" : "Last collected · unconfirmed"}</small>
      </button>)}
    </section>
    <section className="ops-source-grid" aria-label="PE and PC status">
      {states.map(({ id, name, role, state }) => {
        const saved = (props.report?.incidents ?? []).filter(item => item.source === id && !item.resolved);
        const issues = state.feeds.filter(feed => !feed.complete || feed.status !== "COLLECTED");
        const names = [...new Set((props.run?.clusters ?? []).filter(item => item.source.replaceAll("_", "-") === id).map(item => item.name))];
        return <article key={id} className={`ops-source ops-tone-${state.tone}`}>
          <div className="ops-source-heading"><div className="ops-source-icon">{id === "prism-element" ? <Server size={19} /> : <Layers size={19} />}</div><div><h3>{name}</h3><small>{role}</small></div><span className={`ops-pill ${state.verified ? "ops-fresh" : "ops-unknown"}`}>{state.verified ? "Current" : "Unconfirmed"}</span></div>
          <div className="ops-source-body"><div><strong>{state.label}</strong><p>{names.join(" · ") || "Inventory identity unavailable"}</p></div><button className="text-button" onClick={() => props.onOpen(undefined, id)} aria-label={`Review ${name} alerts`}>View alerts <ArrowUpRight size={14} /></button></div>
          <div className="ops-source-meta"><span>{state.verified ? state.critical : saved.filter(item => item.severity === "CRITICAL").length} critical · {state.verified ? state.warning : saved.filter(item => item.severity === "WARNING").length} warning · {state.verified ? state.incidents.length : saved.length} open {state.verified ? "" : "(saved)"}</span><span>{state.feeds.filter(feed => feed.complete && feed.status === "COLLECTED").length}/2 feeds · {ageLabel(state.age)}</span></div>
          {issues.length ? <p className="ops-feed-problem">Collection problem: {issues.map(feed => `${feed.kind}: ${feed.error || feed.status}`).join("; ")}. Review connection diagnostics before assessing health.</p> : null}
        </article>;
      })}
    </section>
    <div className="ops-workspace">
      <section className="ops-queue" id="ops-priority-queue" aria-label="Immediate actions">
        <div className="ops-section-title"><div><span className="ops-kicker">Triage workspace</span><h2>Immediate actions <span>{queue.length}</span></h2></div><button className="text-button" onClick={() => props.onOpen()}>Full incident queue <ArrowUpRight size={14} /></button></div>
        <p className="ops-queue-caption">Critical first. Recovery actions stay visible after source resolution. PE and PC observations remain separate.</p>
        <div className="ops-filters">
          <label className="ops-search"><Search size={15} /><span className="sr-only">Search immediate actions</span><input type="search" placeholder="Search issue, entity or alert ID" value={query} onChange={event => setQuery(event.target.value)} /></label>
          <label><span className="sr-only">Filter action type</span><select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All priorities</option><option value="CRITICAL">Critical</option><option value="WARNING">Warning</option><option value="recovery">Recovery actions</option></select></label>
          <label><span className="sr-only">Filter action source</span><select value={sourceFilter} onChange={event => setSourceFilter(event.target.value)}><option value="all">All sources</option><option value="prism-element">Prism Element</option><option value="prism-central">Prism Central</option></select></label>
        </div>
        <div className="ops-table-wrap"><table className="ops-priority-table"><thead><tr><th scope="col">Priority / source</th><th scope="col">Issue &amp; affected system</th><th scope="col">Immediate next step</th><th scope="col">Action</th></tr></thead><tbody>
          {visible.slice(0, 10).map(({ incident, recovery, confirmed }) => <tr key={incident.id}>
            <td><span className={`ops-pill ops-severity-${incident.severity.toLowerCase()}`}>{incident.severity}</span><small>{incident.source === "prism-central" ? "PC" : "PE"} · {confirmed ? "Current" : "Unconfirmed"}</small></td>
            <td><button className="ops-issue-link" onClick={() => props.onOpen(incident.id)}>{recovery ? "A200335 · Microservices recovery" : incident.title}</button><small>{incident.affected_entities.map(item => item.name || item.id).join(" · ") || "Affected system not reported"}</small>{recovery ? <span className="ops-recovery-tag">{confirmed ? "Recovery incomplete" : "Recovery needs verification"} · source alert {incident.resolved ? "resolved" : "open"}</span> : null}</td>
            <td><p>{!confirmed ? "Refresh monitoring, then confirm the source state and affected services before acting." : recovery ? incident.deployment_diagnostics?.next_actions[0] : incident.triage.steps[0]?.check ?? "Review source evidence and confirm service impact."}</p></td>
            <td><button className="secondary-button" aria-label={recovery ? "Review A200335 recovery" : `Investigate ${incident.title} from ${incident.source}`} onClick={() => props.onOpen(incident.id)}>Investigate <ArrowRight size={14} /></button></td>
          </tr>)}
        </tbody></table></div>
        {!visible.length ? <div className="ops-empty"><Search size={22} /><h3>{queue.length ? "No matching actions" : "No actions in collected evidence"}</h3><p>{queue.length ? "Try another priority, source or search term." : "Refresh monitoring to confirm source visibility. This does not establish complete estate health."}</p>{queue.length ? <button className="secondary-button" onClick={() => { setQuery(""); setFilter("all"); setSourceFilter("all"); }}>Clear filters</button> : null}</div> : null}
        <div className="ops-queue-footer" aria-live="polite">Showing {Math.min(visible.length, 10)} of {visible.length} matching actions{visible.length > 10 ? " · Open the full incident queue for more" : ""}. Recovery entries are not additional Prism alerts.</div>
      </section>
      <aside className="ops-evidence" aria-label="Evidence and monitoring scope">
        <h2>Monitoring confidence</h2>
        <SourcePostureChart report={props.report} />
        <dl><div><dt>Feed coverage</dt><dd>{feedCount}/4 collected <span className={`ops-pill ${posture.verified ? "ops-fresh" : "ops-unknown"}`}>{posture.verified ? "Current" : "Unconfirmed"}</span></dd></div><div><dt>Last collection</dt><dd>{ageLabel(posture.age)}<small>{props.report?.generated_at ? new Date(props.report.generated_at).toLocaleString() : "No timestamp available"}</small></dd></div><div><dt>Connection trust</dt><dd>{props.report?.available ? props.report.tls_mode === "strict" ? "TLS verified" : "TLS unverified · lab only" : "Not evaluated"}</dd></div></dl>
        <h3>Inventory evidence</h3><p>{props.run ? `${props.run.collectors.length - inventoryIssues.length}/${props.run.collectors.length} probes succeeded · ${ageLabel(inventoryAge)}` : "Not collected"}</p><button className="text-button" onClick={inventoryIssues.length ? props.onDiagnostics : props.onInventory}>Review collection <ArrowUpRight size={14} /></button>
        <div className="ops-scope-note"><ShieldCheck size={16} /><p>Read-only monitoring. Alert posture and collection success do not establish infrastructure health or recovery.</p></div>
        <button className="text-button" onClick={props.onEstate}>View cluster estate <ArrowUpRight size={14} /></button>
      </aside>
    </div>
  </div>;
}
