from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256
import json
import ssl
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings
from app.domain.discovery import (
    EndpointDiscoveryResult,
    EndpointKind,
    LabDiscoveryReport,
    ProbeResult,
    ProbeState,
    prism_central_probe_catalogue,
    prism_element_probe_catalogue,
)
from app.domain.inventory import (
    ClusterInventoryItem,
    InventoryCollectorResult,
    InventoryRunReport,
    InventorySource,
    RawArtifactRef,
)
from app.domain.status import HealthStatus, Observation
from app.services.artifacts import write_raw_artifact


class AdapterDisabledError(RuntimeError):
    pass


@dataclass(frozen=True)
class EndpointConfig:
    kind: EndpointKind
    alias: str
    base_url: str
    username: str
    password: str


@dataclass(frozen=True)
class DomainCollectorSpec:
    domain: str
    check_id: str
    path: str
    method: str
    kind: str | None = None


class NutanixReadOnlyAdapter:
    """Read-only Prism discovery boundary.

    Phase 1 intentionally performs only GET probes. It records evidence about
    reachability and candidate API route presence without creating inventory or
    making read-list POST calls.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def assert_live_calls_allowed(self) -> None:
        if self.settings.demo_mode:
            raise AdapterDisabledError("demo mode cannot contact Prism endpoints")
        if not self.settings.read_only_mode:
            raise AdapterDisabledError("write-capable mode is not implemented")

    def discover_versions(self) -> dict[str, str]:
        self.assert_live_calls_allowed()
        report = self.discover()
        return {endpoint.alias: endpoint.state for endpoint in report.endpoints}

    def discover(self) -> LabDiscoveryReport:
        self.assert_live_calls_allowed()
        endpoints = []
        warnings = [
            "Read-only discovery performs GET probes only.",
            "NCC and SSH are outside Phase 1 and remain disabled.",
        ]
        if self.settings.tls_mode == "insecure_skip_verify":
            warnings.append("TLS verification is disabled for this lab run; do not use as production evidence.")

        for endpoint in self._configured_endpoints():
            endpoints.append(self._discover_endpoint(endpoint))

        return LabDiscoveryReport(
            read_only=self.settings.read_only_mode,
            ncc_enabled=self.settings.enable_ncc,
            ssh_enabled=self.settings.enable_ssh,
            endpoints=endpoints,
            warnings=warnings,
        )

    def collect_inventory(self, run_id: str) -> InventoryRunReport:
        self.assert_live_calls_allowed()
        collectors: list[InventoryCollectorResult] = []
        observations: list[Observation] = []

        for endpoint in self._configured_endpoints():
            result = (
                self._collect_pc_inventory(endpoint, run_id)
                if endpoint.kind == EndpointKind.PRISM_CENTRAL
                else self._collect_pe_inventory(endpoint, run_id)
            )
            collectors.append(result)
            observations.append(
                Observation(
                    check_id="HC-003",
                    status=result.status,
                    source=result.source,
                    summary=result.summary,
                    mandatory=True,
                    evidence_ref=result.raw_artifact.uri if result.raw_artifact else None,
                )
            )
            for domain_result in self._collect_domain_inventory(endpoint, run_id):
                collectors.append(domain_result)
                observations.append(
                    Observation(
                        check_id=domain_check_id(domain_result.domain),
                        status=domain_observation_status(domain_result.status),
                        source=domain_result.source,
                        summary=domain_result.summary,
                        mandatory=False,
                        evidence_ref=domain_result.raw_artifact.uri if domain_result.raw_artifact else None,
                    )
                )

        if not collectors:
            observations.append(
                Observation(
                    check_id="HC-003",
                    status=HealthStatus.UNKNOWN,
                    source="configuration",
                    summary="No Prism endpoints are configured for inventory collection.",
                    mandatory=True,
                )
            )

        warnings = [
            "Inventory collection is read-only and stores raw payloads as local evidence artifacts.",
            "NCC and SSH remain disabled.",
        ]
        if self.settings.tls_mode == "insecure_skip_verify":
            warnings.append("TLS verification is disabled for this lab run; evidence is lab-only.")

        return InventoryRunReport(
            run_id=run_id,
            read_only=self.settings.read_only_mode,
            ncc_enabled=self.settings.enable_ncc,
            ssh_enabled=self.settings.enable_ssh,
            collectors=collectors,
            observations=observations,
            warnings=warnings,
        )

    def _configured_endpoints(self) -> list[EndpointConfig]:
        endpoints: list[EndpointConfig] = []
        if self.settings.pc_url:
            endpoints.append(
                EndpointConfig(
                    kind=EndpointKind.PRISM_CENTRAL,
                    alias="prism-central",
                    base_url=self.settings.pc_url,
                    username=self.settings.pc_username,
                    password=self.settings.pc_password,
                )
            )
        if self.settings.pe_url:
            endpoints.append(
                EndpointConfig(
                    kind=EndpointKind.PRISM_ELEMENT,
                    alias="prism-element",
                    base_url=self.settings.pe_url,
                    username=self.settings.pe_username,
                    password=self.settings.pe_password,
                )
            )
        return endpoints

    def _discover_endpoint(self, endpoint: EndpointConfig) -> EndpointDiscoveryResult:
        probes = (
            prism_central_probe_catalogue()
            if endpoint.kind == EndpointKind.PRISM_CENTRAL
            else prism_element_probe_catalogue()
        )
        return EndpointDiscoveryResult(
            kind=endpoint.kind,
            alias=endpoint.alias,
            base_url=endpoint.base_url,
            tls_mode=self.settings.tls_mode,
            probes=[self._run_probe(endpoint, probe) for probe in probes],
        )

    def _run_probe(self, endpoint: EndpointConfig, probe) -> ProbeResult:
        response = self._request(endpoint, probe.method, probe.path)
        body = response.body
        return ProbeResult(
            name=probe.name,
            path=probe.path,
            method=probe.method,
            state=self._state_from_status(response.status_code) if response.status_code else ProbeState.UNAVAILABLE,
            status_code=response.status_code,
            elapsed_ms=response.elapsed_ms,
            content_type=response.content_type,
            body_sha256=sha256(body).hexdigest() if body else None,
            body_size_bytes=len(body),
            error=response.error,
            source=probe.source,
            notes=probe.notes,
        )

    def _collect_pc_inventory(self, endpoint: EndpointConfig, run_id: str) -> InventoryCollectorResult:
        path = "/api/nutanix/v3/clusters/list"
        body = json.dumps({"kind": "cluster", "length": 100, "offset": 0}).encode("utf-8")
        response = self._request(endpoint, "POST", path, body=body)
        return self._inventory_result_from_response(
            endpoint=endpoint,
            run_id=run_id,
            source=InventorySource.PRISM_CENTRAL,
            path=path,
            method="POST",
            response=response,
            parser=self._parse_pc_clusters,
        )

    def _collect_pe_inventory(self, endpoint: EndpointConfig, run_id: str) -> InventoryCollectorResult:
        path = "/PrismGateway/services/rest/v2.0/cluster/"
        response = self._request(endpoint, "GET", path)
        result = self._inventory_result_from_response(
            endpoint=endpoint,
            run_id=run_id,
            source=InventorySource.PRISM_ELEMENT,
            path=path,
            method="GET",
            response=response,
            parser=self._parse_pe_cluster,
        )
        if result.status == HealthStatus.UNKNOWN and result.status_code in {401, 403}:
            fallback_path = "/api/nutanix/v3/clusters/list"
            body = json.dumps({"kind": "cluster", "length": 100, "offset": 0}).encode("utf-8")
            fallback_response = self._request(endpoint, "POST", fallback_path, body=body)
            fallback = self._inventory_result_from_response(
                endpoint=endpoint,
                run_id=run_id,
                source=InventorySource.PRISM_ELEMENT,
                path=fallback_path,
                method="POST",
                response=fallback_response,
                parser=lambda payload, artifact_hash: self._parse_v3_clusters(payload, artifact_hash, InventorySource.PRISM_ELEMENT),
            )
            if fallback.status != HealthStatus.UNKNOWN:
                return fallback
        return result

    def _collect_domain_inventory(self, endpoint: EndpointConfig, run_id: str) -> list[InventoryCollectorResult]:
        specs = (
            pc_domain_collectors()
            if endpoint.kind == EndpointKind.PRISM_CENTRAL
            else pe_domain_collectors()
        )
        source = InventorySource.PRISM_CENTRAL if endpoint.kind == EndpointKind.PRISM_CENTRAL else InventorySource.PRISM_ELEMENT
        return [self._collect_domain(endpoint, run_id, source, spec) for spec in specs]

    def _collect_domain(
        self,
        endpoint: EndpointConfig,
        run_id: str,
        source: InventorySource,
        spec: DomainCollectorSpec,
    ) -> InventoryCollectorResult:
        body = None
        if spec.method == "POST":
            body = json.dumps({"kind": spec.kind, "length": 100, "offset": 0}).encode("utf-8")
        response = self._request(endpoint, spec.method, spec.path, body=body)
        return self._domain_result_from_response(endpoint, run_id, source, spec, response)

    def _domain_result_from_response(
        self,
        endpoint: EndpointConfig,
        run_id: str,
        source: InventorySource,
        spec: DomainCollectorSpec,
        response: "HttpResponse",
    ) -> InventoryCollectorResult:
        raw_artifact = None
        if response.body:
            artifact_path, artifact_hash = write_raw_artifact(
                self.settings.evidence_dir,
                run_id,
                source,
                spec.domain,
                response.body,
            )
            raw_artifact = RawArtifactRef(
                source=source,
                path=spec.path,
                method=spec.method,
                sha256=artifact_hash,
                size_bytes=len(response.body),
                uri=str(artifact_path),
            )

        if response.error:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                domain=spec.domain,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} {spec.domain} collector failed: {response.error}",
                path=spec.path,
                method=spec.method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
                error=response.error,
            )

        if response.status_code and not 200 <= response.status_code < 300:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                domain=spec.domain,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} {spec.domain} collector returned HTTP {response.status_code}.",
                path=spec.path,
                method=spec.method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
            )

        try:
            item_count = count_payload_items(response.body)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                domain=spec.domain,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} {spec.domain} payload could not be interpreted.",
                path=spec.path,
                method=spec.method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
                error=type(error).__name__,
            )

        return InventoryCollectorResult(
            source=source,
            endpoint_alias=endpoint.alias,
            domain=spec.domain,
            status=HealthStatus.HEALTHY,
            summary=f"{endpoint.alias} {spec.domain} collector captured {item_count} record(s).",
            path=spec.path,
            method=spec.method,
            status_code=response.status_code,
            elapsed_ms=response.elapsed_ms,
            item_count=item_count,
            raw_artifact=raw_artifact,
        )

    def _inventory_result_from_response(
        self,
        endpoint: EndpointConfig,
        run_id: str,
        source: InventorySource,
        path: str,
        method: str,
        response: "HttpResponse",
        parser,
    ) -> InventoryCollectorResult:
        raw_artifact = None
        if response.body:
            artifact_path, artifact_hash = write_raw_artifact(
                self.settings.evidence_dir,
                run_id,
                source,
                "inventory",
                response.body,
            )
            raw_artifact = RawArtifactRef(
                source=source,
                path=path,
                method=method,
                sha256=artifact_hash,
                size_bytes=len(response.body),
                uri=str(artifact_path),
            )

        if response.error:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} inventory collector failed: {response.error}",
                path=path,
                method=method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
                error=response.error,
            )

        if response.status_code and not 200 <= response.status_code < 300:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} inventory collector returned HTTP {response.status_code}.",
                path=path,
                method=method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
            )

        try:
            clusters = parser(response.body, raw_artifact.sha256 if raw_artifact else "")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} inventory payload could not be interpreted.",
                path=path,
                method=method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
                error=type(error).__name__,
            )

        if not clusters:
            return InventoryCollectorResult(
                source=source,
                endpoint_alias=endpoint.alias,
                status=HealthStatus.UNKNOWN,
                summary=f"{endpoint.alias} inventory collector returned no clusters.",
                path=path,
                method=method,
                status_code=response.status_code,
                elapsed_ms=response.elapsed_ms,
                raw_artifact=raw_artifact,
            )

        return InventoryCollectorResult(
            source=source,
            endpoint_alias=endpoint.alias,
            status=HealthStatus.HEALTHY,
            summary=f"{endpoint.alias} inventory collector returned {len(clusters)} cluster record(s).",
            path=path,
            method=method,
            status_code=response.status_code,
            elapsed_ms=response.elapsed_ms,
            clusters=clusters,
            raw_artifact=raw_artifact,
        )

    def _parse_pc_clusters(self, body: bytes, artifact_hash: str) -> list[ClusterInventoryItem]:
        return self._parse_v3_clusters(body, artifact_hash, InventorySource.PRISM_CENTRAL)

    def _parse_v3_clusters(self, body: bytes, artifact_hash: str, source: InventorySource) -> list[ClusterInventoryItem]:
        payload = json.loads(body.decode("utf-8"))
        entities = payload.get("entities") or []
        clusters = []
        for entity in entities:
            metadata = entity.get("metadata") or {}
            spec = entity.get("spec") or {}
            status = entity.get("status") or {}
            resources = status.get("resources") or {}
            external_id = str(metadata.get("uuid") or status.get("uuid") or spec.get("uuid") or "")
            name = str(
                spec.get("name")
                or status.get("name")
                or resources.get("name")
                or external_id
                or "unnamed-cluster"
            )
            version = self._version_from_pc_resources(resources)
            if not external_id:
                external_id = name
            clusters.append(
                ClusterInventoryItem(
                    source=source,
                    external_id=external_id,
                    name=name,
                    state=str(status.get("state") or resources.get("state") or "") or None,
                    version=version,
                    raw_artifact_sha256=artifact_hash,
                )
            )
        return clusters

    @staticmethod
    def _version_from_pc_resources(resources: dict[str, object]) -> str | None:
        software_map = ((resources.get("config") or {}).get("software_map") or {}) if isinstance(resources.get("config"), dict) else {}
        nos = software_map.get("NOS") or {}
        if isinstance(nos, dict) and nos.get("version"):
            return str(nos["version"])
        build = ((resources.get("config") or {}).get("build") or {}) if isinstance(resources.get("config"), dict) else {}
        if isinstance(build, dict) and build.get("version"):
            return str(build["version"])
        if resources.get("version"):
            return str(resources["version"])
        return None

    def _parse_pe_cluster(self, body: bytes, artifact_hash: str) -> list[ClusterInventoryItem]:
        payload = json.loads(body.decode("utf-8"))
        external_id = str(
            payload.get("cluster_uuid")
            or payload.get("uuid")
            or payload.get("id")
            or payload.get("clusterExternalDataServicesIpAddress")
            or ""
        )
        name = str(payload.get("name") or payload.get("cluster_name") or external_id or "prism-element")
        version = str(payload.get("version") or payload.get("fullVersion") or payload.get("nccVersion") or "") or None
        return [
            ClusterInventoryItem(
                source=InventorySource.PRISM_ELEMENT,
                external_id=external_id or name,
                name=name,
                state=str(payload.get("state") or "") or None,
                version=version,
                raw_artifact_sha256=artifact_hash,
            )
        ]

    def _request(
        self,
        endpoint: EndpointConfig,
        method: str,
        path: str,
        body: bytes | None = None,
    ) -> "HttpResponse":
        url = urljoin(endpoint.base_url.rstrip("/") + "/", path.lstrip("/"))
        headers = {
            "Accept": "application/json, text/plain;q=0.8, */*;q=0.1",
            "User-Agent": "ClusterAssuranceOrchestrator/0.1 read-only-lab",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if endpoint.username and endpoint.password:
            credential = f"{endpoint.username}:{endpoint.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + b64encode(credential).decode("ascii")

        request = Request(url, data=body, headers=headers, method=method)
        started = perf_counter()
        try:
            with urlopen(request, timeout=10, context=self._ssl_context()) as response:
                response_body = response.read(2 * 1024 * 1024)
                return HttpResponse(
                    status_code=response.status,
                    elapsed_ms=int((perf_counter() - started) * 1000),
                    content_type=response.headers.get("content-type"),
                    body=response_body,
                )
        except HTTPError as error:
            response_body = error.read(2 * 1024 * 1024)
            return HttpResponse(
                status_code=error.code,
                elapsed_ms=int((perf_counter() - started) * 1000),
                content_type=error.headers.get("content-type") if error.headers else None,
                body=response_body,
            )
        except (TimeoutError, URLError, OSError, ssl.SSLError) as error:
            return HttpResponse(
                elapsed_ms=int((perf_counter() - started) * 1000),
                error=type(error).__name__,
            )

    def _ssl_context(self) -> ssl.SSLContext:
        if self.settings.tls_mode == "insecure_skip_verify":
            return ssl._create_unverified_context()
        if self.settings.custom_ca_bundle:
            return ssl.create_default_context(cafile=self.settings.custom_ca_bundle)
        return ssl.create_default_context()

    @staticmethod
    def _state_from_status(status_code: int) -> ProbeState:
        if 200 <= status_code < 300:
            return ProbeState.SUPPORTED
        if status_code in {401, 403}:
            return ProbeState.AUTH_REQUIRED
        if status_code in {404, 405}:
            return ProbeState.UNSUPPORTED
        if 500 <= status_code < 600:
            return ProbeState.UNAVAILABLE
        return ProbeState.UNKNOWN


@dataclass(frozen=True)
class HttpResponse:
    status_code: int | None = None
    elapsed_ms: int | None = None
    content_type: str | None = None
    body: bytes = b""
    error: str | None = None


def pc_domain_collectors() -> list[DomainCollectorSpec]:
    return [
        DomainCollectorSpec(
            domain="storage",
            check_id="HC-STORAGE",
            path="/api/nutanix/v3/storage_containers/list",
            method="POST",
            kind="storage_container",
        ),
        DomainCollectorSpec(
            domain="hardware",
            check_id="HC-HARDWARE",
            path="/api/nutanix/v3/hosts/list",
            method="POST",
            kind="host",
        ),
        DomainCollectorSpec(
            domain="network",
            check_id="HC-NETWORK",
            path="/api/nutanix/v3/subnets/list",
            method="POST",
            kind="subnet",
        ),
        DomainCollectorSpec(
            domain="capacity",
            check_id="HC-CAPACITY",
            path="/api/nutanix/v3/clusters/list",
            method="POST",
            kind="cluster",
        ),
    ]


def pe_domain_collectors() -> list[DomainCollectorSpec]:
    return [
        DomainCollectorSpec(
            domain="storage",
            check_id="HC-STORAGE",
            path="/PrismGateway/services/rest/v2.0/storage_containers/",
            method="GET",
        ),
        DomainCollectorSpec(
            domain="hardware",
            check_id="HC-HARDWARE",
            path="/PrismGateway/services/rest/v2.0/hosts/",
            method="GET",
        ),
        DomainCollectorSpec(
            domain="network",
            check_id="HC-NETWORK",
            path="/PrismGateway/services/rest/v2.0/networks/",
            method="GET",
        ),
        DomainCollectorSpec(
            domain="capacity",
            check_id="HC-CAPACITY",
            path="/PrismGateway/services/rest/v2.0/cluster/",
            method="GET",
        ),
    ]


def domain_check_id(domain: str) -> str:
    return {
        "storage": "HC-STORAGE",
        "hardware": "HC-HARDWARE",
        "network": "HC-NETWORK",
        "capacity": "HC-CAPACITY",
    }.get(domain, "HC-DOMAIN")


def domain_observation_status(status: HealthStatus) -> HealthStatus:
    if status == HealthStatus.HEALTHY:
        return HealthStatus.HEALTHY
    if status == HealthStatus.CRITICAL:
        return HealthStatus.CRITICAL
    return HealthStatus.WARNING


def count_payload_items(body: bytes) -> int:
    payload = json.loads(body.decode("utf-8")) if body else {}
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 1
    entities = payload.get("entities")
    if isinstance(entities, list):
        return len(entities)
    for key in ("storage_containers", "hosts", "entities", "networks", "subnets", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    return 1 if payload else 0
