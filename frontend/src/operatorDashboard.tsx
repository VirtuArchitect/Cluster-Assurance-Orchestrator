import React, { useEffect, useRef, useState } from "react";
import type { MonitoringReport } from "./monitoring";
import type { InventoryRun } from "./main";
import { monitoringPosture, ageSeconds } from "./operational";

const API = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const sources = [{ id: "prism-element", name: "Prism Element", role: "PE · Cluster operations" }, { id: "prism-central", name: "Prism Central", role: "PC · Management plane" }];
const ageLabel = (seconds: number | null) => seconds == null ? "Age unknown" : seconds < 60 ? `${seconds}s ago` : seconds < 3600 ? `${Math.floor(seconds / 60)}m ago` : `${Math.floor(seconds / 3600)}h ago`;

export function OperatorDashboard(props: {
  report: MonitoringReport | null; run: InventoryRun | null; authToken: string; canCollect: boolean;
  onUpdate: (report: MonitoringReport) => void; onOpen: (id?: string, source?: string) => void;
  onDiagnostics: () => void; onEstate: () => void; onInventory: () => void;
}) {
  const posture = monitoringPosture(props.report);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(false);
  useEffect(() => {
    if (!auto || !props.canCollect) return;
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => window.clearInterval(timer);
  }, [auto, props.canCollect, props.authToken]);
  async function refresh() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null);
    try {
      const response = await fetch(`${API}/api/v1/monitoring/collect`, { method: "POST", headers: { Authorization: `Bearer ${props.authToken}` } });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === "string" ? payload.detail : `Collection failed (HTTP ${response.status})`);
      }
      props.onUpdate(await response.json() as MonitoringReport);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Collection failed. Last-known evidence retained."); }
    finally { busyRef.current = false; setBusy(false); }
  }
  const lastKnown = (props.report?.incidents ?? []).filter((item) => item.availability !== "CURRENT" && !item.resolved);
  const inventoryIssues = (props.run?.collectors ?? []).filter((item) => item.status !== "HEALTHY");
  const inventoryAge = ageSeconds(props.run?.generated_at);
  return <div className="operator-dashboard">
    <section className={`watch-summary watch-${posture.tone}`} aria-label="Operations status">
      <div><p className="watch-eyebrow">Operations watch</p><h2>{posture.verified ? posture.critical ? "Critical alerts need investigation" : posture.warning ? "Warnings need investigation" : posture.label : "Refresh monitoring to confirm current status"}</h2>
        <p>{posture.verified ? "Prism-reported alert status across PE and PC. Confirm service impact during triage." : "Saved alerts are shown below. Current PE and PC status cannot be confirmed until fresh, complete monitoring is available."}</p>
        <div className="watch-counts"><span><strong>{props.report?.available ? posture.critical : "—"}</strong> critical</span><span><strong>{props.report?.available ? posture.warning : "—"}</strong> warning</span><span><strong>{props.report?.available ? posture.incidents.length : "—"}</strong> open alert observations</span></div>
        <small>{posture.verified ? "Current collection" : "Last collected evidence"} · {ageLabel(posture.age)}{!posture.complete ? " · Coverage incomplete" : ""}. PE and PC may report the same issue; counts are source observations.</small>
      </div>
      <div className="watch-refresh"><button className="primary-button" disabled={busy || !props.canCollect} onClick={() => void refresh()}>{busy ? "Collecting PE & PC…" : "Refresh PE & PC monitoring"}</button>
        <label className="watch-auto"><input type="checkbox" checked={auto} disabled={!props.canCollect} onChange={(event) => setAuto(event.target.checked)} /> Auto-refresh every 60 seconds</label>
        <small>{props.canCollect ? "Read-only alerts and events. Auto-refresh runs only while this dashboard is open." : "An operator with collection permission is required to refresh monitoring."}</small></div>
    </section>
    {error ? <div className="banner unknown" role="alert">{error} Saved evidence remains visible; freshness has not been reset.</div> : null}
    <section className="watch-source-grid" aria-label="PE and PC status">
      {sources.map((source) => {
        const state = monitoringPosture(props.report, source.id);
        const clusters = (props.run?.clusters ?? []).filter((item) => item.source.replaceAll("_", "-") === source.id);
        const names = [...new Set(clusters.map((item) => item.name))];
        return <article className={`watch-source watch-${state.tone}`} key={source.id}>
          <div className="watch-source-title"><div><p className="watch-eyebrow">{source.role}</p><h2>{source.name}</h2></div><span className={`watch-state watch-${state.tone}`}>{state.verified ? "RECENT EVIDENCE" : "UNCONFIRMED"}</span></div>
          <h3>{state.label}</h3><p className="watch-source-names">{names.length ? names.join(" · ") : "Inventory identity unavailable"}</p>
          <div className="watch-counts"><span><strong>{state.feeds.some((feed) => feed.kind === "alerts" && feed.complete) ? state.critical : "—"}</strong> critical</span><span><strong>{state.feeds.some((feed) => feed.kind === "alerts" && feed.complete) ? state.warning : "—"}</strong> warning</span><span><strong>{state.feeds.some((feed) => feed.kind === "alerts" && feed.complete) ? state.incidents.length : "—"}</strong> open</span></div>
          <p>{state.verified ? state.incidents[0]?.title ?? "Prism reports no open alerts in this collection." : `Last collected ${ageLabel(state.age)}. ${state.complete ? "Evidence is stale or unavailable." : "Alerts or events collection is incomplete."}`}</p>
          <div className="watch-source-footer"><small>Alerts: {state.feeds.find((feed) => feed.kind === "alerts")?.complete ? "collected" : "unavailable"} · Events: {state.feeds.find((feed) => feed.kind === "events")?.complete ? "collected" : "unavailable"} · {ageLabel(state.age)}</small><button className="secondary-button" onClick={() => props.onOpen(undefined, source.id)}>Review {source.id === "prism-element" ? "PE" : "PC"} alerts →</button></div>
          <small className="watch-scope">Alert status only. Storage resilience, performance and workload recovery require targeted checks.</small>
        </article>;
      })}
    </section>
    <section className="panel watch-actions" aria-label="Immediate actions">
      <div className="watch-section-heading"><div><h2>Immediate actions</h2><p>{posture.verified ? "Critical first. Open an issue for source evidence, detailed checks and recovery criteria." : "1. Refresh monitoring. Then investigate the saved priorities below; their current state is unconfirmed."}</p></div><button className="secondary-button" onClick={() => props.onOpen()}>All incidents →</button></div>
      {posture.incidents.length ? <ol className="watch-action-list">{posture.incidents.slice(0, 5).map((incident) => <li key={incident.id}>
        <div><span className={`status ${incident.severity.toLowerCase()}`}>{incident.severity}</span><span className="watch-source-label">{incident.source === "prism-central" ? "PC" : "PE"}{!posture.verified ? " · last collected" : ""}</span><h3>{incident.title}</h3><p>{incident.affected_entities.map((item) => item.name || item.id).join(" · ") || "Affected entity not reported"}</p><p><strong>First check:</strong> {incident.triage.steps[0]?.check ?? "Review the original Prism alert and verify workload impact."}</p></div>
        <button className="secondary-button" aria-label={`Investigate ${incident.title} from ${incident.source}`} onClick={() => props.onOpen(incident.id)}>Investigate →</button>
      </li>)}</ol> : <p className="watch-empty">{posture.verified ? "No current open alerts reported by Prism. This does not establish complete cluster health." : "No current alert evidence available. Refresh monitoring before assessing the estate."}</p>}
      {posture.incidents.length > 5 ? <p>{posture.incidents.length - 5} more open observations in the incident queue.</p> : null}
      {lastKnown.length ? <p>{lastKnown.length} additional last-known alert observations have unavailable source evidence. <button className="text-button" onClick={() => props.onOpen()}>Review incident history</button></p> : null}
    </section>
    <section className="watch-evidence-bar" aria-label="Monitoring limitations and collection status">
      <div><strong>Evidence trust</strong><p>{props.report?.available ? props.report.tls_mode === "strict" ? "TLS verified for this monitoring collection." : "TLS unverified · dev/lab evidence." : "No monitoring evidence collected."} No infrastructure changes or alert acknowledgements.</p></div>
      <div><strong>Inventory collection</strong><p>{props.run ? `${props.run.collectors.length - inventoryIssues.length}/${props.run.collectors.length} probes succeeded · ${ageLabel(inventoryAge)}. ${inventoryIssues.length ? `${inventoryIssues.length} collection problems.` : "Collection success is separate from cluster health."}` : "Inventory has not been collected."}</p><button className="text-button" onClick={inventoryIssues.length ? props.onDiagnostics : props.onInventory}>{inventoryIssues.length ? "Review collection problems →" : "Review inventory collection →"}</button></div>
      <div><strong>Cluster identities</strong><p>PE and PC represent different views of the estate. Confirm affected systems before taking action.</p><button className="text-button" onClick={props.onEstate}>View estate →</button></div>
    </section>
  </div>;
}
