"""Bounded, read-only evidence for PC microservices deployment incidents."""
from datetime import UTC, datetime
import json
from urllib.parse import urlsplit

from app.services.artifacts import public_artifact_ref, write_raw_artifact


def collect_pc_diagnostics(adapter, pc, pe, run_id):
    result = {"status": "UNKNOWN", "observed_at": datetime.now(UTC).isoformat(),
              "run_id": run_id, "evidence": [], "tasks": [], "prerequisites": None,
              "conclusion": "Deployment blocker has not been established.", "next_actions": []}

    def request(endpoint, method, path, body=None, label="diagnostics"):
        response = adapter._request(endpoint, method, path, body)
        evidence = {"source": endpoint.alias, "method": method, "path": path,
                    "http_status": response.status_code, "elapsed_ms": response.elapsed_ms}
        if body:
            evidence["request_body"] = json.loads(body)
        if response.body:
            file, digest = write_raw_artifact(adapter.settings.evidence_dir, run_id,
                                             endpoint.kind.value, label, response.body)
            evidence.update(artifact=public_artifact_ref(file), sha256=digest, size_bytes=len(response.body))
        result["evidence"].append(evidence)
        if response.error or response.status_code != 200:
            raise ValueError(f"{endpoint.alias}: {response.error or 'HTTP ' + str(response.status_code)}")
        payload = json.loads(response.body)
        if not isinstance(payload, dict) or payload.get("error_info", {}).get("count", 0):
            raise ValueError("Unrecognized diagnostic response")
        return payload

    try:
        tasks, seen, expected = [], set(), None
        for page in range(20):
            offset = page * 100
            payload = request(pc, "POST", "/api/nutanix/v3/tasks/list",
                              json.dumps({"kind": "task", "length": 100, "offset": offset}).encode(),
                              f"microservices-tasks-{offset}")
            total = payload["metadata"]["total_matches"]
            if type(total) is not int or total < 0 or (expected is not None and total != expected):
                raise ValueError("Changing or invalid task pagination total")
            expected = total
            items = payload["entities"]
            if not isinstance(items, list):
                raise ValueError("Missing task list")
            for task in items:
                identity = task.get("uuid")
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise ValueError("Missing or repeated task identity")
                seen.add(identity)
                tasks.append(task)
            if len(tasks) == total:
                break
            if not items or len(tasks) > total:
                raise ValueError("Incomplete task pagination")
        else:
            raise ValueError("Task collection exceeded 2000 records")
        deployments = [t for t in tasks if t.get("operation_type") == "PC Microservice Infrastructure Deployment"]
        # Parse dates before sorting; malformed dates must not select historical evidence as current.
        def created(task):
            value = datetime.fromisoformat(task["creation_time"].replace("Z", "+00:00"))
            if value.tzinfo is None:
                raise ValueError("Task creation time lacks timezone")
            return value
        root = max(deployments, key=created) if deployments else None
        checks = [t for t in tasks if root and t.get("operation_type") == "CMSP Prechecks"
                  and (t.get("parent_task_uuid") == root["uuid"] or created(t) == created(root))]
        check = max(checks, key=created) if checks else None
        selected = [t for t in (root, check) if t]
        for task in selected:
            if any(task.get(key) is not None and not isinstance(task[key], str) for key in (
                "uuid", "operation_type", "status", "creation_time", "last_update_time", "progress_message", "error_detail")):
                raise ValueError("Unrecognized deployment task fields")
            result["tasks"].append({k: task.get(k) for k in (
                "uuid", "operation_type", "status", "creation_time", "last_update_time", "progress_message", "error_detail")})
        result["task_correlation"] = "Parent task UUID or identical deployment creation time; not alert-to-task causality"
        result["task_records_collected"] = len(tasks)
        if pe is None:
            raise ValueError("No configured PE endpoint; prerequisites cannot be verified")
        cluster = request(pe, "GET", "/PrismGateway/services/rest/v2.0/cluster/", label="microservices-pe-prerequisites")
        required = ("cluster_external_ipaddress", "cluster_external_data_services_ipaddress")
        if any(key not in cluster for key in required) or not cluster.get("uuid"):
            raise ValueError("PE cluster identity or prerequisite fields were not reported")
        vip, data_ip = (cluster[key] for key in required)
        if any(value is not None and not isinstance(value, str) for value in (vip, data_ip)):
            raise ValueError("Unrecognized PE prerequisite value")
        host = urlsplit(pe.base_url).hostname
        result["prerequisites"] = {"pe_host": host, "cluster_uuid": cluster["uuid"],
                                   "cluster_vip": vip, "data_services_ip": data_ip,
                                   "fqdn_status": "Not verified by this endpoint"}
        error = str(check.get("error_detail") or check.get("progress_message") or "") if check else ""
        matches_pe = bool(host and f"'{host}'" in error and "Prism Element" in error)
        blockers = []
        if root and root.get("status") in ("RUNNING", "FAILED") and check and check.get("status") == "FAILED" and matches_pe:
            if not vip and "Cluster Virtual IP or Cluster FQDN" in error:
                blockers.append("CMSP precheck reports missing PE cluster VIP/FQDN; PE API confirms VIP is unset (FQDN unverified)")
            if not data_ip and "Cluster Data Services IP" in error:
                blockers.append("CMSP precheck reports missing PE Data Services IP; PE API confirms it is unset")
        result["blockers"] = blockers
        result["status"] = "BLOCKED" if blockers else "NO_CONFIRMED_BLOCKER"
        result["conclusion"] = ("Latest deployment precheck is blocked by PE network prerequisites. This is a likely contributor to A200335, not proof of its runtime root cause."
                                if blockers else "No matching PE prerequisite blocker confirmed by these checks. This does not prove microservices health.")
        result["next_actions"] = ([
            "Plan the missing PE cluster VIP/FQDN and Data Services IP using validated available addresses, DNS and installed-release guidance; this console makes no configuration changes.",
            "Review the latest parent deployment state before retrying. A RUNNING parent with a FAILED precheck is not successful deployment; use the supported recovery procedure or Nutanix Support if stuck.",
            "After an approved correction, rerun version-supported prechecks and validate microservices health, PC functions and fresh source alert resolution.",
        ] if blockers else ["Review PC component health, task errors and the version-matched runbook with an authorized administrator; do not infer health from task-list success."])
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        result["status"] = "UNKNOWN"
        result["error"] = str(error)[:300]
        result["blockers"] = []
        result["next_actions"] = ["Restore complete PC task and matched PE prerequisite evidence before claiming a blocker is present or cleared."]
    return result
