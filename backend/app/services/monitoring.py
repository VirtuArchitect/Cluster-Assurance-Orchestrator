"""Read-only Prism incident collection. Source resolution is never inferred from absence."""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import html
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4

from app.adapters.nutanix import NutanixReadOnlyAdapter
from app.core.config import Settings
from app.services.artifacts import public_artifact_ref, write_raw_artifact
from app.services.pc_diagnostics import collect_pc_diagnostics

COLLECTION_LOCK = Lock()
PAGE_SIZE = 100
MAX_PAGES = 20


def latest_monitoring(evidence_dir: str | Path) -> dict:
    paths = sorted(Path(evidence_dir).glob("monitoring-run-*.json"), reverse=True)
    if not paths:
        return {"available": False, "incidents": [], "events": [], "collectors": [], "generated_at": None}
    # A damaged latest snapshot must be visible, not silently replaced by older success.
    result = json.loads(paths[0].read_text(encoding="utf-8"))
    result["available"] = True
    return result


def collect_monitoring(settings: Settings) -> dict:
    adapter = NutanixReadOnlyAdapter(settings)
    adapter.assert_live_calls_allowed()
    if not COLLECTION_LOCK.acquire(blocking=False):
        raise RuntimeError("A monitoring collection is already running")
    try:
        previous = latest_monitoring(settings.evidence_dir)
        run_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        collectors, alerts, events = [], [], []
        for endpoint in adapter._configured_endpoints():
            # Prevent a changed target from inheriting incidents from the old endpoint.
            source_key = sha256(f"{endpoint.kind.value}:{endpoint.base_url.rstrip('/')}".encode()).hexdigest()[:16]
            for kind in ("alerts", "events"):
                collector, records = collect_feed(adapter, endpoint, kind, run_id, source_key)
                collectors.append(collector)
                if not collector["complete"]:
                    continue
                normalized = []
                try:
                    for record, artifact in records:
                        normalized.append(normalize_record(record, endpoint.alias, source_key, kind, artifact, now))
                except (ValueError, TypeError, AttributeError, OverflowError):
                    collector.update(complete=False, status="UNKNOWN", error="Unrecognized Prism record schema")
                    continue
                (alerts if kind == "alerts" else events).extend(normalized)

        incidents = reconcile_incidents(previous.get("incidents", []), alerts, collectors, now, run_id)
        events.sort(key=lambda item: item.get("occurred_at") or "", reverse=True)
        for incident in incidents:
            incident["triage"] = triage_for(incident)
            incident["related_events"] = correlated_events(incident, events)
            incident.pop("deployment_diagnostics", None)
            incident.pop("recurrence", None)
            if incident["triage"]["category"] == "Prism Central microservices infrastructure" and incident.get("occurred_at"):
                candidates = [old for old in incidents if old["id"] != incident["id"]
                    and old["source_key"] == incident["source_key"] and old["check_id"] == incident["check_id"]
                    and old["cluster_id"] == incident["cluster_id"]
                    and {e["id"] for e in old["affected_entities"] if e["id"]} & {e["id"] for e in incident["affected_entities"] if e["id"]}
                    and old["resolved"] and old.get("source_resolved_at")
                    and old["source_resolved_at"] < incident["occurred_at"]]
                if candidates:
                    old = max(candidates, key=lambda item: item["source_resolved_at"])
                    incident["recurrence"] = {key: old.get(key) for key in (
                        "source_id", "occurred_at", "last_occurrence_at", "source_resolved_at",
                        "auto_resolved", "resolved_by_username", "availability", "observed_at", "evidence")}
        # Source resolution does not establish deployment recovery. Share one fresh
        # endpoint-scoped diagnostic across current observations, including resolved ones.
        targets = [i for i in incidents if i["source"] == "prism-central"
                   and i["availability"] == "CURRENT" and i["triage"]["category"] == "Prism Central microservices infrastructure"]
        if targets:
            endpoints = adapter._configured_endpoints()
            pc = next(e for e in endpoints if e.alias == "prism-central")
            pe = next((e for e in endpoints if e.alias == "prism-element"), None)
            diagnostics = collect_pc_diagnostics(adapter, pc, pe, run_id)
            for incident in targets:
                incident["deployment_diagnostics"] = diagnostics
                if diagnostics["status"] == "BLOCKED":
                    incident["triage"]["steps"].insert(0, {
                        "check": "Review the observed CMSP deployment prerequisite blocker: " + "; ".join(diagnostics["blockers"]),
                        "expected": "Required PE network settings are verified and the deployment precheck passes",
                        "if_failed": diagnostics["next_actions"][0],
                    })
        active = [item for item in incidents if item["availability"] == "CURRENT" and item["resolved"] is False]
        summary = {
            "critical": sum(item["severity"] == "CRITICAL" for item in active),
            "warning": sum(item["severity"] == "WARNING" for item in active),
            "open": len(active),
            "unavailable": sum(item["availability"] != "CURRENT" for item in incidents),
        }
        result = {
            "available": True, "run_id": run_id, "generated_at": now,
            "completed_at": datetime.now(UTC).isoformat(), "read_only": True,
            "tls_mode": settings.tls_mode, "ncc_enabled": False, "ssh_enabled": False,
            "scope": "Prism alerts/events and targeted read-only PC deployment/PE prerequisite diagnostics; not a complete infrastructure-health evaluation",
            "status": "COLLECTED" if collectors and all(c["complete"] for c in collectors) else "UNKNOWN",
            "summary": summary, "collectors": collectors, "incidents": incidents, "events": events,
        }
        root = Path(settings.evidence_dir)
        root.mkdir(parents=True, exist_ok=True)
        name = f"monitoring-run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}-{run_id}.json"
        temporary = root / (name + ".tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(root / name)
        return result
    finally:
        COLLECTION_LOCK.release()


def collect_feed(adapter, endpoint, kind: str, run_id: str, source_key: str) -> tuple[dict, list]:
    collector = {"source": endpoint.alias, "source_key": source_key, "kind": kind,
                 "status": "UNKNOWN", "complete": False, "count": 0, "pages": [], "error": None}
    records, seen, expected_total = [], set(), None
    for page in range(1, MAX_PAGES + 1):
        path = f"/PrismGateway/services/rest/v2.0/{kind}/?count={PAGE_SIZE}&page={page}"
        response = adapter._request(endpoint, "GET", path)
        evidence = {"method": "GET", "path": path, "http_status": response.status_code,
                    "elapsed_ms": response.elapsed_ms}
        if response.body:
            file, digest = write_raw_artifact(adapter.settings.evidence_dir, run_id, endpoint.kind.value,
                                              f"{kind}-page-{page}", response.body)
            evidence.update(artifact=public_artifact_ref(file), sha256=digest, size_bytes=len(response.body))
        collector["pages"].append(evidence)
        if response.error or response.status_code != 200:
            collector["error"] = response.error or f"HTTP {response.status_code}"
            return collector, []
        try:
            payload = json.loads(response.body)
            if not isinstance(payload, dict) or not isinstance(payload.get("entities"), list):
                raise ValueError("Expected an entities list")
            if payload.get("error_info", {}).get("count", 0):
                raise ValueError("Prism returned an error envelope")
            total = payload["metadata"]["total_entities"]
            if type(total) is not int or total < 0 or (expected_total is not None and total != expected_total):
                raise ValueError("Invalid or changing pagination total")
            expected_total = total
            items = payload["entities"]
            for item in items:
                identity = str(item.get("id") or item.get("uuid") or "")
                if not identity or identity in seen:
                    raise ValueError("Missing or repeated record identity")
                seen.add(identity)
                records.append((item, evidence))
            collector["count"] = len(records)
            if len(records) == total:
                collector.update(complete=True, status="COLLECTED")
                return collector, records
            if not items or len(records) > total:
                raise ValueError("Incomplete or inconsistent pagination")
        except (ValueError, TypeError, KeyError, AttributeError):
            collector["error"] = "Malformed, changing or incomplete Prism response; no clear-health claim"
            return collector, []
    collector["error"] = f"Collection exceeded {MAX_PAGES} pages; source coverage is incomplete"
    return collector, []


def source_time(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1_000_000, UTC).isoformat() if value > 0 else None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC).isoformat() if parsed.tzinfo is None else parsed.astimezone(UTC).isoformat()


def normalize_record(record: dict, source: str, source_key: str, kind: str, artifact: dict, now: str) -> dict:
    identity = str(record.get("id") or record.get("uuid") or "")
    if not identity or (kind == "alerts" and type(record.get("resolved")) is not bool):
        raise ValueError("Missing alert identity or resolution status")
    severity = {"kcritical": "CRITICAL", "critical": "CRITICAL", "kwarning": "WARNING", "warning": "WARNING",
                "kinfo": "INFO", "info": "INFO", "kaudit": "INFO", "audit": "INFO"}.get(str(record.get("severity", "")).lower(), "UNKNOWN")
    context = {str(key): str(value)[:2048] for key, value in
               zip(record.get("context_types") or [], record.get("context_values") or [])
               if not re.search(r"password|token|secret|authorization|cookie", str(key), re.I)}
    message = render_vendor_text(str(record.get("message") or record.get("detailed_message") or record.get("alert_title") or "Prism record"), context)
    title = render_vendor_text(str(record.get("alert_title") or message), context)
    if "{" in title:
        title = message
    entities = [{"id": str(item.get("uuid") or item.get("id") or ""),
                 "name": str(item.get("entity_name") or item.get("uuid") or "Unnamed entity"),
                 "type": str(item.get("entity_type") or "unknown")}
                for item in record.get("affected_entities", []) if isinstance(item, dict)]
    return {
        "id": sha256(f"{source_key}:{kind}:{identity}".encode()).hexdigest()[:32],
        "source_id": identity, "source": source, "source_key": source_key, "kind": kind,
        "title": title[:300], "message": message, "severity": severity,
        "resolved": record.get("resolved"), "acknowledged": record.get("acknowledged") is True,
        "auto_resolved": record.get("auto_resolved") if type(record.get("auto_resolved")) is bool else None,
        "resolved_by_username": str(record.get("resolved_by_username") or "")[:200],
        "cluster_id": str(record.get("originating_cluster_uuid") or record.get("cluster_uuid") or ""),
        "check_id": str(record.get("check_id") or ""), "affected_entities": entities,
        "occurred_at": source_time(record.get("created_time_stamp_in_usecs")),
        "last_occurrence_at": source_time(record.get("last_occurrence_time_stamp_in_usecs")),
        "source_resolved_at": source_time(record.get("resolved_time_stamp_in_usecs")),
        "observed_at": now, "availability": "CURRENT", "evidence": artifact,
        "vendor_possible_causes": record.get("possible_causes") or [],
        "vendor_details": record.get("alert_details"),
        "vendor_description": render_vendor_text(str(record.get("detailed_message") or ""), context),
        "vendor_guidance": {"possible_cause": context.get("cause"), "recommended_action": context.get("resolution"), "reported_impact": context.get("impact_list")},
        "source_versions": {"software": context.get("nos_version"), "ncc": context.get("ncc_version")},
        "unresolved_parameters": sorted(set(re.findall(r"\{([a-zA-Z0-9_]+)\}", message))),
    }


def render_vendor_text(text: str, context: dict) -> str:
    # Literal substitution only. No format/eval, HTML execution, or source commands.
    rendered = re.sub(r"\{([a-zA-Z0-9_]+)\}", lambda match: context.get(match.group(1), match.group(0)), text)
    rendered = re.sub(r"<br\s*/?>", "\n", rendered, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", rendered))


def reconcile_incidents(previous: list, current: list, collectors: list, now: str, run_id: str) -> list:
    old = {item["id"]: item for item in previous}
    merged = []
    for item in current:
        prior = old.pop(item["id"], None)
        state = "RESOLVED_IN_PRISM" if item["resolved"] else "ACKNOWLEDGED" if item["acknowledged"] else "OPEN"
        item["lifecycle"] = state
        item["first_seen_at"] = prior["first_seen_at"] if prior else now
        history = list(prior.get("history", [])) if prior else []
        if not prior or prior.get("lifecycle") != state or prior.get("severity") != item["severity"] or prior.get("availability") != "CURRENT":
            history.append({"at": now, "state": state, "severity": item["severity"], "run_id": run_id, "evidence": item["evidence"]})
        item["history"] = history[-100:]
        item["last_seen_run_id"] = run_id
        merged.append(item)
    for item in old.values():
        item = dict(item)
        matching = [c for c in collectors if c["source_key"] == item["source_key"] and c["kind"] == "alerts"]
        availability = "NOT_OBSERVED" if matching and matching[0]["complete"] else "UNAVAILABLE"
        # Disappearance, a failed request, or a removed connection never means resolution.
        if item.get("availability") != availability:
            item["history"] = (item.get("history", []) + [{"at": now, "state": availability,
                                "severity": item["severity"], "run_id": run_id}])[-100:]
        item["availability"] = availability
        merged.append(item)
    return sorted(merged, key=lambda i: (i.get("resolved") is True, {"CRITICAL": 0, "WARNING": 1}.get(i["severity"], 2), i["title"]))


def correlated_events(incident: dict, events: list) -> list:
    ids = {e["id"] for e in incident.get("affected_entities", []) if e["id"]}
    timestamp = incident.get("last_occurrence_at") or incident.get("occurred_at")
    if not ids or not timestamp:
        return []
    time = datetime.fromisoformat(timestamp)
    return [event for event in events if event.get("occurred_at")
            and abs((datetime.fromisoformat(event["occurred_at"]) - time).total_seconds()) <= 3600
            and ids.intersection(e["id"] for e in event["affected_entities"])][:30]


def triage_for(incident: dict) -> dict:
    text = f"{incident['title']} {incident['message']}".lower()
    pc_microservices = incident.get("source") in ("prism-central", "prism_central") and (
        "microservices infrastructure is not in healthy state" in text
        or bool(re.search(r"(?:^|::)A?200335$", str(incident.get("check_id", "")), re.I)))
    cvm_home = bool(re.search(r"/home(?:/[^\s,;]*)?(?=$|[\s,;.:])", text)) and bool(re.search(r"\bcvm\b|controller\s+vm|controller\s+virtual\s+machine", text)) and any(word in text for word in ("disk space", "disk usage", "filesystem", "file system", "partition", "inode", "space usage"))
    if pc_microservices:
        category, checks = "Prism Central microservices infrastructure", [
            ("Confirm PC Microservices Infrastructure status and affected PC services; compare with direct PE access and establish user impact", "The affected PC instance, alert A200335/check ID, first/last occurrence and impacted management functions are recorded", "Escalate unavailable PC functions or repeated failures. A PC management-plane alert alone does not establish AHV/VM or PE failure"),
            ("Review the Microservices Infrastructure widget and deployment/upgrade tasks for the installed PC release", "Infrastructure is enabled where required and deployment/upgrade tasks have completed successfully", "Capture the failed task, timestamp and error. If deployment is incomplete, follow the version-matched recovery procedure with support; do not repeatedly enable or redeploy the platform"),
            ("Check PC sizing, memory pressure, filesystem byte/inode headroom and associated resource alerts", "PC resources meet installed-release requirements and no resource exhaustion explains the service failure", "Capture allocation, usage trends and relevant alerts; prepare a reviewed correction. Do not resize PC disks, delete files or restart services automatically"),
            ("Check related DNS, NTP, certificate and network alerts; for deployment failures, verify required endpoint or image-registry reachability using installed-release guidance", "Dependencies are reachable with valid trust and synchronized time; relevant tasks report no dependency failure", "Record the failing dependency and time window; use a reviewed correction without bypassing TLS or changing firewall rules blindly"),
            ("Have an authorized PC administrator or Nutanix Support inspect version-supported microservices health output and relevant service/pod status, events and logs", "The failing component and error are identified, or independent diagnostics confirm services are healthy", "Preserve health output, component identity, restart counts and time-scoped logs. This console runs no SSH, NCC or Kubernetes commands; do not delete pods, restart services or redeploy as a diagnostic shortcut"),
            ("Review KB 20379 applicability for A200335 with Nutanix Support using the exact PC version and independent health evidence", "Support confirms whether the documented false-positive case applies or identifies a genuine platform fault", "An alert title or reachable PC UI is insufficient to declare a false positive. Keep the incident actionable until applicability and service health are established"),
            ("After a reviewed correction, verify microservices health, affected PC functions and a fresh PC alert collection", "Deployment tasks have completed, relevant service checks are healthy, affected functions work and the source alert is resolved", "Escalate persistent or recurring failures with PC/AOS/NCC versions, alert/check IDs, task errors, resource/dependency evidence and time-scoped diagnostics"),
        ]
    elif cvm_home:
        category, checks = "CVM /home filesystem", [
            ("Confirm the affected CVM and /home mount from the original Prism alert; an authorized administrator can inspect df -h /home and df -i /home on that CVM", "The mount, byte usage, inode usage and available space are recorded; compare with the alert's reported threshold and installed-release guidance", "Separate exhausted bytes from exhausted inodes; capture outputs and the CVM identity for support. This console does not run SSH commands"),
            ("Identify growth within the affected filesystem using a scoped, read-only directory usage inspection; review recent support bundles, uploads, logs and upgrade activity", "The growing directory and its owner are identified without traversing other mounts or treating Stargate data as disposable", "Use an approved version-matched diagnostic procedure; large recursive scans can add load. If ownership or cleanup eligibility is unclear, engage Nutanix Support"),
            ("Compare filesystem totals with directory usage and review existing disk_usage_check and inode_usage_check results where available", "Byte/inode pressure is explained and relevant checks agree with the affected mount", "If totals disagree, ask support to inspect open-but-deleted files and mount visibility. Do not restart services to release space without an approved procedure"),
            ("Prepare a reviewed cleanup or correction using the installed AOS/NCC guidance and the original alert's KB", "Only explicitly approved obsolete artifacts are removed or relocated, with evidence retained and the source of recurring growth corrected", "Do not delete arbitrary files, logs, snapshots, or /home/nutanix/data content; do not resize CVM disks or restart/reboot services as an automatic fix. Escalate near exhaustion, rapid growth or service impact"),
            ("After an approved correction, recheck df -h /home and df -i /home and obtain fresh PE/PC alerts plus the relevant targeted check", "Usage is below the applicable alert threshold with stable headroom, the source alert is resolved, and the operator has verified service impact", "If pressure persists or recurs, escalate with timestamps, mount/usage outputs, growth evidence, alert/check IDs and installed versions"),
        ]
    elif any(word in text for word in ("configured resource", "memory availability", "pc_vm_resource", "pc_vm_memory")):
        category, checks = "Prism Central sizing and memory", [
            ("Compare PC allocation and deployment size with the installed release requirements", "vCPU, memory and deployment topology meet the supported sizing guidance", "Capture allocated resources, PC version and the source health check; prepare a reviewed sizing correction"),
            ("Inspect current memory pressure and related PC service alerts", "PC services are stable and the relevant memory/sizing check passes", "Escalate impact and sizing evidence; do not resize or restart PC automatically"),
        ]
    elif any(word in text for word in ("default password", "password based ssh", "password-based ssh")):
        category, checks = "Security configuration", [
            ("Identify the account or access setting named by the original Prism alert", "The affected identity and applicable security baseline are established", "Escalate to the credential/security owner without exposing passwords or weakening authentication"),
            ("Follow the approved credential or SSH-access change procedure", "A fresh source check confirms the insecure configuration is corrected", "Use a reviewed change with dependency checks; this view performs no credential changes"),
        ]
    elif any(word in text for word in ("incompatible", "unsupported version")):
        category, checks = "Software compatibility", [
            ("Compare AOS, hypervisor, PC and NCC versions with the applicable support matrix", "The combination is supported for the installed releases", "Capture exact versions and check applicability with Nutanix support"),
            ("Review related alerts, lifecycle history and the supported upgrade path", "A supported correction and its prerequisites are understood", "Plan an approved change; do not infer that an immediate upgrade is safe"),
        ]
    elif any(word in text for word in ("resilien", "replicat", "rebuild", "fault toleran")):
        category, checks = "Data resiliency", [
            ("Check Prism data resiliency and remaining failure tolerance", "All required replicas and failure tolerance are available", "Escalate if another failure cannot be tolerated; defer disruptive maintenance"),
            ("Inspect failed disks/nodes, rebuild progress and resilient capacity", "Rebuild is progressing and sufficient headroom remains", "Collect affected component IDs and Nutanix alert details; engage support"),
        ]
    elif any(word in text for word in ("capacity", "disk space", "storage space", "utilization")):
        category, checks = "Capacity", [
            ("Compare physical usage, resilient capacity and rebuild reservation", "Headroom satisfies the cluster's configured resiliency policy", "Identify the constrained resource; escalate capacity risk before further changes"),
            ("Review growth, snapshots and recent workload changes", "The source of growth is understood", "Prepare a reviewed expansion or capacity-recovery plan; do not delete data automatically"),
        ]
    elif any(word in text for word in ("latency", "iops", "throughput")):
        category, checks = "Storage performance", [
            ("Compare sustained latency with workload impact and peer entities", "Scope and duration of impact are established", "Inspect affected workloads, rebuilds, hardware and network events"),
            ("Correlate recent changes with IOPS, throughput and latency", "A supported explanation is evidenced", "Capture graphs and event times for escalation; correlation alone is not root cause"),
        ]
    elif any(word in text for word in ("disk", "hardware", "power supply", "fan", "temperature")):
        category, checks = "Hardware", [
            ("Identify the affected host, disk or hardware component in Prism", "The alert maps to an exact component and current state", "Capture serial/slot and current alerts; verify redundancy before maintenance"),
            ("Inspect associated resiliency and relevant NCC results", "No unresolved related failure remains", "Use the matching hardware KB and Nutanix support guidance"),
        ]
    elif any(word in text for word in ("sync", "connectivity", "heartbeat", "network", "dns", "ntp", "certificate")):
        category, checks = "Connectivity and dependencies", [
            ("Compare direct PE visibility with PC visibility", "Both report recent evidence for the same cluster", "Separate management-path failure from cluster failure"),
            ("Inspect relevant DNS, NTP, certificate and network alerts", "Dependencies are healthy and clocks/certificates are valid", "Collect reachability and sync evidence before changing configuration"),
        ]
    elif any(word in text for word in ("service", "cvm", "reboot", "microservice")):
        category, checks = "Services and availability", [
            ("Identify the affected PC, host or CVM and compare peer state", "Service availability and workload impact are established", "Check maintenance/reboot events and current critical alerts"),
            ("Inspect the relevant NCC/service health result and version-matched KB", "The affected service is stable and the specific check passes", "Capture service/check outputs and engage Nutanix support; do not restart services automatically"),
        ]
    else:
        category, checks = "Prism alert investigation", [
            ("Read the original Prism alert and affected entities", "The symptom, scope and source are understood", "Capture the alert ID, check ID, versions and current evidence"),
            ("Review vendor possible causes, the applicable KB and nearby events", "A cause is supported by independent evidence", "Escalate with an evidence bundle if applicability or cause is uncertain"),
        ]
    references = incident["message"] + " " + incident.get("vendor_description", "") + " " + json.dumps(incident.get("vendor_guidance", {}))
    kb_ids = sorted(set(re.findall(r"\bKB[-\s]?(\d{3,6})\b", references, re.I)))
    return {"category": category, "basis": "Curated symptom-based guidance; not a confirmed root cause",
            "steps": [{"check": c, "expected": e, "if_failed": f} for c, e, f in checks],
            "resolution_criteria": (["Independent PC microservices diagnostics are healthy and deployment/upgrade tasks have completed", "Previously affected PC functions are verified by the operator; any false-positive determination is supported by version applicability and diagnostics"] if pc_microservices else ["Affected CVM /home byte and inode usage are below applicable thresholds with stable headroom", "The relevant disk/inode check passes and recurring growth is addressed"] if cvm_home else []) + ["Prism explicitly reports the source alert resolved", "Fresh collection succeeds for the affected source", "Relevant targeted check passes and workload impact is verified by the operator"],
            "curated_references": ([{"title": "Nutanix KB 20379 — A200335 false-positive applicability", "url": "https://portal.nutanix.com/kb/20379", "basis": "Curated reference from Nutanix's published KB catalogue. Portal access and installed-version applicability review required; not a confirmed diagnosis."}] if pc_microservices else []),
            "escalation": "Escalate critical impact, lost resiliency, repeated failures or unclear cause to the incident owner / Nutanix support.",
            "safety": "Read-only investigation. No automatic reboot, service restart, disk removal, deletion, or Prism acknowledgement/resolution.",
            "kb_links": [f"https://portal.nutanix.com/kb/{kb}" for kb in kb_ids],
            "reference": "https://portal.nutanix.com/", "applicability": "Confirm guidance against installed AOS, PC and NCC versions."}
