import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  Eye,
  EyeOff,
  Filter,
  FileJson,
  Gauge,
  History,
  KeyRound,
  ListChecks,
  LockKeyhole,
  LogOut,
  ClipboardList,
  Moon,
  Network,
  Plus,
  RefreshCw,
  Settings,
  SearchCheck,
  ShieldCheck,
  Sun,
  TerminalSquare,
  Trash2,
  Users
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";
const ASSET_BASE = import.meta.env.BASE_URL ?? "/";
const APP_VERSION = "0.1.0";
const APP_VERSION_TAG = `v${APP_VERSION}`;

type HealthStatus = "CRITICAL" | "UNKNOWN" | "WARNING" | "OVERDUE" | "HEALTHY";
type ThemeMode = "light" | "dark";
type SettingsPageId = "storage" | "connections" | "readiness" | "rbac" | "ncc" | "audit" | "about";
type PageId =
  | "dashboard"
  | "triage"
  | "estate"
  | "runs"
  | "findings"
  | "schedules"
  | "evidence"
  | "settings";

type Cluster = {
  source: string;
  external_id: string;
  name: string;
  state: string | null;
  version: string | null;
  raw_artifact_sha256: string;
  collected_at: string;
};

type Collector = {
  endpoint_alias: string;
  source: string;
  domain?: string;
  status: HealthStatus;
  status_code: number | null;
  summary: string;
  elapsed_ms: number | null;
  item_count?: number | null;
  method: string;
  path: string;
  raw_artifact: {
    uri: string;
    sha256: string;
    size_bytes: number;
  } | null;
};

type Observation = {
  check_id: string;
  status: HealthStatus;
  source: string;
  summary: string;
  evidence_ref: string | null;
};

type InventoryRun = {
  run_id: string;
  status: HealthStatus;
  maturity: string;
  generated_at: string;
  read_only: boolean;
  ncc_enabled: boolean;
  ssh_enabled: boolean;
  clusters: Cluster[];
  collectors: Collector[];
  observations: Observation[];
  warnings: string[];
};

type SchedulePreview = {
  schedule: {
    name: string;
    recurrence: string;
    start_time: string;
    timezone: string;
    profile: {
      name: string;
      version: number;
      profile_version_id: string;
    };
    target_cluster_ids: string[];
  };
  occurrences: Array<{
    occurrence_at: string;
    idempotency_key: string;
    status: string;
    reason: string;
    runnable_cluster_ids: string[];
    blocked_cluster_ids: string[];
  }>;
  active_locks: Array<{
    cluster_id: string;
    owner_run_id: string;
    expires_at: string;
  }>;
};

type NccProfile = {
  profile_id: string;
  name: string;
  command_display: string;
  timeout_minutes: number;
  state: string;
};

type NccProfilesResponse = {
  profiles: NccProfile[];
  transport: string;
  execution: string;
};

type NccPlan = {
  status: string;
  reason: string;
  command_hash: string;
  ncc_enabled: boolean;
  ssh_enabled: boolean;
  profile: NccProfile;
  warnings: string[];
};

type EvidenceManifest = {
  run_id: string;
  product_version: string;
  profile_version: string;
  generated_at: string;
  manifest_sha256: string;
  result_summary: Record<string, string | number | boolean>;
  artifacts: Array<{
    artifact_type: string;
    uri: string;
    sha256: string;
    size_bytes: number;
  }>;
};

type IntegrationReport = {
  maturity: string;
  outbound_enabled: boolean;
  correlation_key: string;
  adapters: Array<{
    adapter_id: string;
    name: string;
    category: string;
    state: string;
    direction: string;
    summary: string;
    required_settings: string[];
    supported_events: string[];
    safety_notes: string[];
  }>;
};

type SecurityReadinessReport = {
  maturity: string;
  gates: Array<{
    gate_id: string;
    name: string;
    status: string;
    summary: string;
    evidence: string[];
  }>;
  roles: Array<{
    permission: string;
    viewer: boolean;
    operator: boolean;
    admin: boolean;
  }>;
  open_risks: string[];
};

type CatalogueCheck = {
  check_id: string;
  name: string;
  source: string;
  default_frequency: string;
  failure_outcome: string;
  mandatory: boolean;
};

type CatalogueResponse = {
  version: string;
  checks: CatalogueCheck[];
};

type ManagedConnection = {
  id: string;
  name: string;
  type: "Prism Central" | "Prism Element";
  url: string;
  username: string;
  secretSet: boolean;
  tlsMode: string;
  status: string;
  lastCheckedAt: string | null;
};

type ManagedRole = {
  id: string;
  name: string;
  permissions: string;
};

type ManagedUser = {
  id: string;
  username: string;
  name: string;
  email: string;
  roleId: string;
  roleName: string;
  status: "Active" | "Disabled";
  passwordSet: boolean;
  passwordUpdatedAt: string | null;
};

type ManagedSchedule = {
  id: string;
  name: string;
  enabled: boolean;
  definition: {
    schedule_id: string;
    name: string;
    profile: {
      profile_id: string;
      name: string;
      version: number;
      definition_hash: string;
      checks: string[];
      timeout_minutes: number;
    };
    target_cluster_ids: string[];
    timezone: string;
    recurrence: "daily" | "weekly" | "on_demand";
    start_time: string;
    weekly_day: number;
    enabled: boolean;
    misfire_policy: string;
    misfire_grace_minutes: number;
  };
  updated_at: string;
};

type ScheduleRunHistory = {
  id: string;
  schedule_id: string;
  occurrence_at: string;
  target_cluster_ids: string[];
  status: string;
  started_at: string;
  completed_at: string | null;
  run_id: string | null;
  evidence_path: string | null;
  message: string;
};

type HealthRunHistoryItem = {
  run_id: string | null;
  run_type: string;
  status: HealthStatus;
  generated_at: string | null;
  age_seconds: number | null;
  path: string;
  cluster_count: number;
  collector_count: number;
  collector_failure_count: number;
  collector_failures: Array<{ source: string; endpoint_alias: string; domain?: string; status: string; status_code: number | null; summary: string }>;
  warnings: string[];
};

type SupportStatus = {
  mode: {
    environment: string;
    demo_mode: boolean;
    read_only_mode: boolean;
    ncc_enabled: boolean;
    ssh_enabled: boolean;
    tls_mode: string;
  };
  api_url: string;
  config_source: string;
  evidence_directory: string;
  admin_database: string;
  latest_run: {
    available: boolean;
    run_id: string | null;
    run_type: string | null;
    status: string;
    generated_at: string | null;
    age_seconds: number | null;
    path?: string;
  };
  collector_failures: Array<{ source: string; endpoint_alias: string; domain?: string; status: string; status_code: number | null; summary: string }>;
  warnings: string[];
};

type RetentionReport = {
  policy: { retention_days: number; minimum_runs: number };
  evidence_dir: string;
  inventory_runs: number;
  deletable_runs: number;
  deletable_files?: string[];
  deleted_files?: string[];
};

type DatabaseBackup = {
  name: string;
  created_at: string;
  size_bytes: number;
  size_label: string;
};

type StorageStatus = {
  backend: string;
  status: string;
  data_directory: string;
  database_location: string;
  credentials_hidden: boolean;
  postgres_enabled: boolean;
  backup_supported: boolean;
  retention: {
    audit_days: number;
    execution_days: number;
    evidence_days: number;
    evidence_minimum_runs: number;
  };
  backups: DatabaseBackup[];
};

type AlertStatus = {
  enabled: boolean;
  trustworthy_evidence: boolean;
  reason: string;
  email: { configured: boolean; target: string; state: string };
  webhook: { configured: boolean; state: string };
  later_adapters: Record<string, string>;
};

type ScheduleRequestInput = {
  schedule_id: string;
  name: string;
  profile?: ManagedSchedule["definition"]["profile"];
  target_cluster_ids: string[];
  timezone: string;
  recurrence: ManagedSchedule["definition"]["recurrence"];
  start_time: string;
  weekly_day: number;
  enabled: boolean;
  misfire_policy?: string;
  misfire_grace_minutes?: number;
};

type AuthUser = {
  id: string;
  username: string;
  role_id: string;
  role_name: string;
  permissions: string[];
};

type AuditEvent = {
  id: string;
  occurred_at: string;
  actor_username: string | null;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, string | number | boolean | null>;
};

type OperationalDomain = {
  id: "inventory" | "storage" | "hardware" | "network" | "capacity";
  label: string;
  status: HealthStatus;
  value: string;
  detail: string;
  coverage: number;
  evidence: string;
  action: string;
  actionPage: PageId;
};

const pages: Array<{ id: PageId; label: string; icon: React.ComponentType<{ size?: number }> }> = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "triage", label: "Operator Triage", icon: CheckCircle2 },
  { id: "estate", label: "Cluster Estate", icon: Database },
  { id: "runs", label: "Health Runs", icon: Activity },
  { id: "findings", label: "Findings", icon: SearchCheck },
  { id: "schedules", label: "Schedules", icon: CalendarClock },
  { id: "evidence", label: "Evidence", icon: FileJson },
  { id: "settings", label: "Settings", icon: Settings }
];

const navGroups: Array<{ label: string; itemIds: PageId[] }> = [
  { label: "Overview", itemIds: ["dashboard", "triage"] },
  { label: "Assure", itemIds: ["estate", "runs", "findings", "schedules", "evidence"] },
  { label: "Admin", itemIds: ["settings"] }
];

const demoUser: AuthUser = {
  id: "demo-admin",
  username: "admin",
  role_id: "admin",
  role_name: "Admin",
  permissions: ["all_permissions"]
};

const demoRun: InventoryRun = {
  run_id: "demo-run-20260922T163000Z",
  status: "WARNING",
  maturity: "static demo evidence",
  generated_at: "2026-09-22T16:30:00Z",
  read_only: true,
  ncc_enabled: false,
  ssh_enabled: false,
  clusters: [
    {
      source: "prism-central",
      external_id: "demo-prod-a",
      name: "NTNX-PROD-A",
      state: "COMPLETE",
      version: "6.8.x",
      raw_artifact_sha256: "demo-sha256-prod-a",
      collected_at: "2026-09-22T16:30:00Z"
    },
    {
      source: "prism-element",
      external_id: "demo-edge-a",
      name: "NTNX-EDGE-A",
      state: "COMPLETE",
      version: "6.8.x",
      raw_artifact_sha256: "demo-sha256-edge-a",
      collected_at: "2026-09-22T16:30:00Z"
    },
    {
      source: "prism-element",
      external_id: "demo-lab-a",
      name: "NTNX-LAB-A",
      state: "COMPLETE",
      version: "6.7.x",
      raw_artifact_sha256: "demo-sha256-lab-a",
      collected_at: "2026-09-22T16:30:00Z"
    }
  ],
  collectors: [
    {
      endpoint_alias: "Demo Prism Central",
      source: "prism-central",
      domain: "inventory",
      status: "HEALTHY",
      status_code: 200,
      summary: "Inventory collector returned 3 cluster record(s).",
      elapsed_ms: 311,
      item_count: 3,
      method: "POST",
      path: "/api/nutanix/v3/clusters/list",
      raw_artifact: { uri: "demo://evidence/inventory/prism-central.json", sha256: "demo-inventory", size_bytes: 18342 }
    },
    {
      endpoint_alias: "Demo Prism Central",
      source: "prism-central",
      domain: "storage",
      status: "WARNING",
      status_code: 200,
      summary: "One storage container is above the demo warning threshold.",
      elapsed_ms: 264,
      item_count: 8,
      method: "POST",
      path: "/api/nutanix/v3/storage_containers/list",
      raw_artifact: { uri: "demo://evidence/storage/prism-central.json", sha256: "demo-storage", size_bytes: 15320 }
    },
    {
      endpoint_alias: "Demo Prism Element",
      source: "prism-element",
      domain: "hardware",
      status: "HEALTHY",
      status_code: 200,
      summary: "No demo node, disk or CVM hardware faults detected.",
      elapsed_ms: 228,
      item_count: 12,
      method: "GET",
      path: "/PrismGateway/services/rest/v2.0/hosts",
      raw_artifact: { uri: "demo://evidence/hardware/prism-element.json", sha256: "demo-hardware", size_bytes: 24622 }
    },
    {
      endpoint_alias: "Demo Prism Element",
      source: "prism-element",
      domain: "network",
      status: "HEALTHY",
      status_code: 200,
      summary: "Demo host NIC and network collector returned expected payloads.",
      elapsed_ms: 219,
      item_count: 6,
      method: "GET",
      path: "/PrismGateway/services/rest/v2.0/networks",
      raw_artifact: { uri: "demo://evidence/network/prism-element.json", sha256: "demo-network", size_bytes: 10455 }
    },
    {
      endpoint_alias: "Demo Prism Central",
      source: "prism-central",
      domain: "capacity",
      status: "WARNING",
      status_code: 200,
      summary: "Demo CPU headroom is below the target planning margin.",
      elapsed_ms: 333,
      item_count: 3,
      method: "POST",
      path: "/api/nutanix/v3/clusters/list",
      raw_artifact: { uri: "demo://evidence/capacity/prism-central.json", sha256: "demo-capacity", size_bytes: 18342 }
    }
  ],
  observations: [
    {
      check_id: "storage-container-headroom",
      status: "WARNING",
      source: "storage",
      summary: "One demo storage container is above the target capacity margin.",
      evidence_ref: "demo://evidence/storage/prism-central.json"
    },
    {
      check_id: "capacity-cpu-headroom",
      status: "WARNING",
      source: "capacity",
      summary: "CPU headroom requires review before production readiness sign-off.",
      evidence_ref: "demo://evidence/capacity/prism-central.json"
    },
    {
      check_id: "hardware-fault-posture",
      status: "HEALTHY",
      source: "hardware",
      summary: "No demo hardware fault payloads were reported.",
      evidence_ref: "demo://evidence/hardware/prism-element.json"
    },
    {
      check_id: "network-link-state",
      status: "HEALTHY",
      source: "network",
      summary: "Demo network collector returned expected link-state evidence.",
      evidence_ref: "demo://evidence/network/prism-element.json"
    }
  ],
  warnings: ["Static GitHub Pages demo data is illustrative and does not contact Prism."]
};

const demoSchedule: SchedulePreview = {
  schedule: {
    name: "Daily Standard Lab Preview",
    recurrence: "daily",
    start_time: "06:00",
    timezone: "Europe/Berlin",
    profile: {
      name: "Standard Read-only Assurance",
      version: 1,
      profile_version_id: "demo-profile-v1"
    },
    target_cluster_ids: ["demo-prod-a", "demo-edge-a", "demo-lab-a"]
  },
  occurrences: [
    {
      occurrence_at: "2026-09-23T06:00:00+02:00",
      idempotency_key: "demo-daily-20260923",
      status: "ready",
      reason: "All demo target clusters are available for this occurrence.",
      runnable_cluster_ids: ["demo-prod-a", "demo-edge-a", "demo-lab-a"],
      blocked_cluster_ids: []
    }
  ],
  active_locks: []
};

const demoNccProfiles: NccProfilesResponse = {
  transport: "disabled",
  execution: "planning-only",
  profiles: [
    { profile_id: "ncc-health-checks", name: "NCC Health Checks", command_display: "ncc health_checks run_all", timeout_minutes: 60, state: "planned" },
    { profile_id: "ncc-pre-upgrade", name: "NCC Pre-upgrade", command_display: "ncc health_checks run_all --preupgrade", timeout_minutes: 90, state: "planned" }
  ]
};

const demoNccPlan: NccPlan = {
  status: "blocked",
  reason: "NCC execution is gated in the public demo.",
  command_hash: "demo-command-hash",
  ncc_enabled: false,
  ssh_enabled: false,
  profile: demoNccProfiles.profiles[0],
  warnings: ["Planning surface only. No SSH transport is active."]
};

const demoManifest: EvidenceManifest = {
  run_id: demoRun.run_id,
  product_version: APP_VERSION,
  profile_version: "demo-profile-v1",
  generated_at: demoRun.generated_at,
  manifest_sha256: "demo-manifest-sha256",
  result_summary: { status: demoRun.status, clusters: demoRun.clusters.length, collectors: demoRun.collectors.length, demo: true },
  artifacts: [
    { artifact_type: "inventory", uri: "demo://evidence/inventory/prism-central.json", sha256: "demo-inventory", size_bytes: 18342 },
    { artifact_type: "storage", uri: "demo://evidence/storage/prism-central.json", sha256: "demo-storage", size_bytes: 15320 },
    { artifact_type: "hardware", uri: "demo://evidence/hardware/prism-element.json", sha256: "demo-hardware", size_bytes: 24622 }
  ]
};

const demoIntegrations: IntegrationReport = {
  maturity: "planned",
  outbound_enabled: false,
  correlation_key: "demo-correlation-key",
  adapters: [
    {
      adapter_id: "email",
      name: "Email",
      category: "notification",
      state: "planned",
      direction: "outbound",
      summary: "Email alerts are planned once evidence is trustworthy.",
      required_settings: ["SMTP host", "sender", "recipient"],
      supported_events: ["collector_failure", "readiness_gate_open"],
      safety_notes: ["Disabled in static demo."]
    },
    {
      adapter_id: "webhook",
      name: "Webhook",
      category: "notification",
      state: "planned",
      direction: "outbound",
      summary: "Webhook delivery will support generic operational receivers.",
      required_settings: ["target URL", "secret"],
      supported_events: ["health_run_completed"],
      safety_notes: ["Disabled in static demo."]
    }
  ]
};

const demoReadiness: SecurityReadinessReport = {
  maturity: "lab",
  gates: [
    { gate_id: "tls", name: "TLS verification", status: "HEALTHY", summary: "Demo connections use trusted placeholders.", evidence: ["settings/connections"] },
    { gate_id: "rbac", name: "Role-based access model", status: "HEALTHY", summary: "Local RBAC is enabled in the demo model.", evidence: ["settings/rbac"] },
    { gate_id: "ncc", name: "NCC execution transport", status: "UNKNOWN", summary: "NCC execution remains gated.", evidence: ["settings/ncc"] },
    { gate_id: "uat", name: "Controlled UAT", status: "WARNING", summary: "Production claims require real lab evidence.", evidence: ["evidence/latest"] }
  ],
  roles: [
    { permission: "view_dashboard", viewer: true, operator: true, admin: true },
    { permission: "view_evidence", viewer: true, operator: true, admin: true },
    { permission: "run_read_only_inventory", viewer: false, operator: true, admin: true },
    { permission: "manage_connections", viewer: false, operator: false, admin: true },
    { permission: "manage_rbac", viewer: false, operator: false, admin: true }
  ],
  open_risks: ["Static demo evidence is illustrative and should not be used for production readiness decisions."]
};

const demoCatalogue: CatalogueResponse = {
  version: "demo-catalogue-v1",
  checks: [
    { check_id: "cluster_inventory", name: "Cluster inventory", source: "Prism", default_frequency: "daily", failure_outcome: "UNKNOWN", mandatory: true },
    { check_id: "storage_capacity", name: "Storage capacity", source: "Prism", default_frequency: "daily", failure_outcome: "WARNING", mandatory: true },
    { check_id: "hardware_faults", name: "Hardware faults", source: "Prism", default_frequency: "daily", failure_outcome: "WARNING", mandatory: true },
    { check_id: "network_state", name: "Network state", source: "Prism", default_frequency: "daily", failure_outcome: "WARNING", mandatory: true },
    { check_id: "ncc_gate", name: "NCC gate", source: "NCC", default_frequency: "planned", failure_outcome: "UNKNOWN", mandatory: false }
  ]
};

const demoSupportStatus: SupportStatus = {
  mode: {
    environment: "github-pages-demo",
    demo_mode: true,
    read_only_mode: true,
    ncc_enabled: false,
    ssh_enabled: false,
    tls_mode: "strict"
  },
  api_url: "static demo",
  config_source: "GitHub Pages build",
  evidence_directory: "not exposed",
  admin_database: "static demo data",
  latest_run: {
    available: true,
    run_id: demoRun.run_id,
    run_type: "static-demo",
    status: demoRun.status,
    generated_at: demoRun.generated_at,
    age_seconds: 420,
    path: "demo://evidence/latest"
  },
  collector_failures: demoRun.collectors.filter((collector) => collector.status !== "HEALTHY").map((collector) => ({
    source: collector.source,
    endpoint_alias: collector.endpoint_alias,
    domain: collector.domain,
    status: collector.status,
    status_code: collector.status_code,
    summary: collector.summary
  })),
  warnings: ["Public demo mode is static and does not contact Prism or a backend API."]
};

const demoHealthRunHistory: HealthRunHistoryItem[] = [
  {
    run_id: demoRun.run_id,
    run_type: "static-demo",
    status: demoRun.status,
    generated_at: demoRun.generated_at,
    age_seconds: 420,
    path: "demo://evidence/latest",
    cluster_count: demoRun.clusters.length,
    collector_count: demoRun.collectors.length,
    collector_failure_count: demoRun.collectors.filter((collector) => collector.status !== "HEALTHY").length,
    collector_failures: demoSupportStatus.collector_failures,
    warnings: demoRun.warnings
  },
  {
    run_id: "demo-run-20260921T163000Z",
    run_type: "scheduled",
    status: "HEALTHY",
    generated_at: "2026-09-21T16:30:00Z",
    age_seconds: 86820,
    path: "demo://evidence/previous",
    cluster_count: 3,
    collector_count: 5,
    collector_failure_count: 0,
    collector_failures: [],
    warnings: []
  }
];

const demoRetention: RetentionReport = {
  policy: { retention_days: 30, minimum_runs: 10 },
  evidence_dir: "not exposed",
  inventory_runs: 2,
  deletable_runs: 0,
  deletable_files: [],
  deleted_files: []
};

const demoAlerts: AlertStatus = {
  enabled: false,
  trustworthy_evidence: false,
  reason: "Alert delivery is disabled in the static public demo.",
  email: { configured: false, target: "not configured", state: "planned" },
  webhook: { configured: false, state: "planned" },
  later_adapters: { Checkmk: "planned", ServiceNow: "planned" }
};

const demoRoles: ManagedRole[] = [
  { id: "viewer", name: "Viewer", permissions: "view_dashboard, view_evidence" },
  { id: "operator", name: "Operator", permissions: "view_dashboard, view_evidence, run_read_only_inventory, plan_ncc_runs" },
  { id: "admin", name: "Admin", permissions: "all_permissions" }
];

const demoUsers: ManagedUser[] = [
  { id: "demo-admin", username: "admin", name: "Demo Admin", email: "admin@example.invalid", roleId: "admin", roleName: "Admin", status: "Active", passwordSet: true, passwordUpdatedAt: "2026-09-22T16:00:00Z" },
  { id: "demo-operator", username: "operator", name: "Demo Operator", email: "operator@example.invalid", roleId: "operator", roleName: "Operator", status: "Active", passwordSet: true, passwordUpdatedAt: "2026-09-22T16:00:00Z" }
];

const demoConnections: ManagedConnection[] = [
  { id: "demo-pc", name: "Demo Prism Central", type: "Prism Central", url: "https://prism-central.example.invalid:9440", username: "readonly", secretSet: true, tlsMode: "strict", status: "READY", lastCheckedAt: "2026-09-22T16:29:00Z" },
  { id: "demo-pe", name: "Demo Prism Element", type: "Prism Element", url: "https://prism-element.example.invalid:9440", username: "readonly", secretSet: true, tlsMode: "strict", status: "READY", lastCheckedAt: "2026-09-22T16:29:30Z" }
];

const demoAuditEvents: AuditEvent[] = [
  { id: "audit-demo-1", occurred_at: "2026-09-22T16:20:00Z", actor_username: "admin", action: "connection.test", target_type: "connection", target_id: "demo-pc", details: { status: "READY", demo: true } },
  { id: "audit-demo-2", occurred_at: "2026-09-22T16:15:00Z", actor_username: "admin", action: "storage.backup.list", target_type: "storage", target_id: "postgres", details: { demo: true } }
];

const demoStorageStatus: StorageStatus = {
  backend: "postgres",
  status: "healthy",
  data_directory: "configured locally",
  database_location: "postgresql://postgres:5432/cao",
  credentials_hidden: true,
  postgres_enabled: true,
  backup_supported: true,
  retention: {
    audit_days: 90,
    execution_days: 180,
    evidence_days: 30,
    evidence_minimum_runs: 10
  },
  backups: [
    { name: "cao-demo-20260922-163000.dump", created_at: "2026-09-22T16:30:00Z", size_bytes: 524288, size_label: "512 KB" },
    { name: "cao-demo-20260921-163000.dump", created_at: "2026-09-21T16:30:00Z", size_bytes: 393216, size_label: "384 KB" }
  ]
};

const demoSchedules: ManagedSchedule[] = [
  {
    id: "daily-standard-lab-preview",
    name: "Daily Standard Lab Preview",
    enabled: true,
    updated_at: "2026-09-22T16:10:00Z",
    definition: {
      schedule_id: "daily-standard-lab-preview",
      name: "Daily Standard Lab Preview",
      profile: {
        profile_id: "standard-read-only",
        name: "Standard Read-only Assurance",
        version: 1,
        definition_hash: "demo-profile-hash",
        checks: demoCatalogue.checks.map((check) => check.check_id),
        timeout_minutes: 60
      },
      target_cluster_ids: ["demo-prod-a", "demo-edge-a", "demo-lab-a"],
      timezone: "Europe/Berlin",
      recurrence: "daily",
      start_time: "06:00",
      weekly_day: 0,
      enabled: true,
      misfire_policy: "skip",
      misfire_grace_minutes: 30
    }
  }
];

const demoScheduleHistory: ScheduleRunHistory[] = [
  { id: "schedule-run-demo-1", schedule_id: "daily-standard-lab-preview", occurrence_at: "2026-09-22T06:00:00+02:00", target_cluster_ids: ["demo-prod-a", "demo-edge-a", "demo-lab-a"], status: "WARNING", started_at: "2026-09-22T06:00:03+02:00", completed_at: "2026-09-22T06:02:15+02:00", run_id: demoRun.run_id, evidence_path: "demo://evidence/latest", message: "Completed with demo capacity warnings." },
  { id: "schedule-run-demo-2", schedule_id: "daily-standard-lab-preview", occurrence_at: "2026-09-21T06:00:00+02:00", target_cluster_ids: ["demo-prod-a", "demo-edge-a", "demo-lab-a"], status: "HEALTHY", started_at: "2026-09-21T06:00:02+02:00", completed_at: "2026-09-21T06:01:58+02:00", run_id: "demo-run-20260921T163000Z", evidence_path: "demo://evidence/previous", message: "Completed successfully." }
];

function App() {
  const [authToken, setAuthToken] = useState(() => STATIC_DEMO ? (window.sessionStorage.getItem("cao-token") ?? "static-demo-token") : window.sessionStorage.getItem("cao-token") ?? "");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => {
    const storedUser = window.sessionStorage.getItem("cao-user");
    if (STATIC_DEMO && !storedUser) {
      return demoUser;
    }
    return storedUser ? JSON.parse(storedUser) as AuthUser : null;
  });
  const [activePage, setActivePage] = useState<PageId>("dashboard");
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const storedTheme = window.localStorage.getItem("cao-theme");
    return storedTheme === "dark" ? "dark" : "light";
  });
  const [run, setRun] = useState<InventoryRun | null>(null);
  const [schedule, setSchedule] = useState<SchedulePreview | null>(null);
  const [nccProfiles, setNccProfiles] = useState<NccProfilesResponse | null>(null);
  const [nccPlan, setNccPlan] = useState<NccPlan | null>(null);
  const [manifest, setManifest] = useState<EvidenceManifest | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationReport | null>(null);
  const [readiness, setReadiness] = useState<SecurityReadinessReport | null>(null);
  const [catalogue, setCatalogue] = useState<CatalogueResponse | null>(null);
  const [supportStatus, setSupportStatus] = useState<SupportStatus | null>(null);
  const [healthRunHistory, setHealthRunHistory] = useState<HealthRunHistoryItem[]>([]);
  const [retention, setRetention] = useState<RetentionReport | null>(null);
  const [alerts, setAlerts] = useState<AlertStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (authToken) {
      void loadConsoleData();
    }
  }, [authToken]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("cao-theme", theme);
  }, [theme]);

  async function loadConsoleData() {
    setLoading(true);
    setError(null);
    setNccPlan(null);
    if (STATIC_DEMO) {
      setRun(demoRun);
      setSchedule(demoSchedule);
      setNccProfiles(demoNccProfiles);
      setNccPlan(demoNccPlan);
      setManifest(demoManifest);
      setIntegrations(demoIntegrations);
      setReadiness(demoReadiness);
      setCatalogue(demoCatalogue);
      setSupportStatus(demoSupportStatus);
      setHealthRunHistory(demoHealthRunHistory);
      setRetention(demoRetention);
      setAlerts(demoAlerts);
      setLoading(false);
      return;
    }
    try {
      const [runResult, scheduleResult, profilesResult, manifestResult, integrationsResult, readinessResult, catalogueResult, supportResult, historyResult, retentionResult, alertsResult] =
        await Promise.allSettled([
          fetchJson<InventoryRun>("/api/v1/lab/inventory-runs/latest", {}, authToken),
          fetchJson<SchedulePreview>("/api/v1/schedules/preview/default", {}, authToken),
          fetchJson<NccProfilesResponse>("/api/v1/ncc/profiles", {}, authToken),
          fetchJson<EvidenceManifest>("/api/v1/evidence/manifest/latest", {}, authToken),
          fetchJson<IntegrationReport>("/api/v1/integrations/status", {}, authToken),
          fetchJson<SecurityReadinessReport>("/api/v1/security/readiness", {}, authToken),
          fetchJson<CatalogueResponse>("/api/v1/catalogue", {}, authToken),
          fetchJson<SupportStatus>("/api/v1/support/status", {}, authToken),
          fetchJson<HealthRunHistoryItem[]>("/api/v1/health-runs/history", {}, authToken),
          fetchJson<RetentionReport>("/api/v1/evidence/retention", {}, authToken),
          fetchJson<AlertStatus>("/api/v1/alerts/status", {}, authToken)
        ]);

      const latestRun = unwrap(runResult, setRun);
      unwrap(scheduleResult, setSchedule);
      const profiles = unwrap(profilesResult, setNccProfiles);
      unwrap(manifestResult, setManifest);
      unwrap(integrationsResult, setIntegrations);
      unwrap(readinessResult, setReadiness);
      unwrap(catalogueResult, setCatalogue);
      unwrap(supportResult, setSupportStatus);
      if (historyResult.status === "fulfilled") {
        setHealthRunHistory(historyResult.value);
      } else {
        setHealthRunHistory([]);
      }
      unwrap(retentionResult, setRetention);
      unwrap(alertsResult, setAlerts);

      const authFailure = [runResult, scheduleResult, profilesResult, manifestResult, integrationsResult, readinessResult, catalogueResult, supportResult, historyResult, retentionResult, alertsResult]
        .find((result) => result.status === "rejected" && isAuthError(result.reason));
      if (authFailure) {
        expireSession();
        return;
      }

      const firstProfile = profiles?.profiles[0];
      const firstCluster = latestRun?.clusters[0];
      if (firstProfile && firstCluster) {
        const plan = await fetchJson<NccPlan>("/api/v1/ncc/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            profile_id: firstProfile.profile_id,
            cluster_id: firstCluster.external_id
          })
        }, authToken);
        setNccPlan(plan);
      }

      const firstFailure = [runResult, scheduleResult, profilesResult, manifestResult, integrationsResult, readinessResult, catalogueResult, supportResult, historyResult]
        .find((result) => result.status === "rejected");
      if (firstFailure?.status === "rejected") {
        setError(firstFailure.reason instanceof Error ? firstFailure.reason.message : "Some console data could not be loaded.");
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load console data.");
      setRun(null);
      setSchedule(null);
      setNccProfiles(null);
      setNccPlan(null);
      setManifest(null);
      setIntegrations(null);
      setReadiness(null);
      setCatalogue(null);
      setSupportStatus(null);
      setHealthRunHistory([]);
      setRetention(null);
      setAlerts(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleSignIn(username: string, password: string): Promise<string | null> {
    if (STATIC_DEMO) {
      if (username.toLowerCase() !== "admin" || password !== "ChangeMe123!") {
        return "Use admin / ChangeMe123! for the public demo.";
      }
      window.sessionStorage.setItem("cao-token", "static-demo-token");
      window.sessionStorage.setItem("cao-user", JSON.stringify(demoUser));
      setAuthToken("static-demo-token");
      setCurrentUser(demoUser);
      return null;
    }
    try {
      const session = await fetchJson<{ token: string; user: AuthUser }>("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      window.sessionStorage.setItem("cao-token", session.token);
      window.sessionStorage.setItem("cao-user", JSON.stringify(session.user));
      setAuthToken(session.token);
      setCurrentUser(session.user);
      return null;
    } catch (signInError) {
      return signInError instanceof Error ? signInError.message : "Unable to sign in.";
    }
  }

  async function handleSignOut() {
    if (authToken) {
      await fetchJson<{ status: string }>("/api/v1/auth/logout", { method: "POST" }, authToken).catch(() => null);
    }
    expireSession();
  }

  function expireSession() {
    window.sessionStorage.removeItem("cao-token");
    window.sessionStorage.removeItem("cao-user");
    setAuthToken("");
    setCurrentUser(null);
    setActivePage("dashboard");
  }

  const problemCollectors = useMemo(
    () => run?.collectors.filter((collector) => collector.status !== "HEALTHY") ?? [],
    [run]
  );

  const activeMeta = pages.find((page) => page.id === activePage) ?? pages[0];

  if (!authToken) {
    return <LoginPage onSignIn={handleSignIn} />;
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="sidebar-header">
          <button
            className="brand"
            type="button"
            onClick={() => setActivePage("dashboard")}
            aria-label="Go to dashboard"
          >
            <img src={`${ASSET_BASE}zto-logo-mark.svg`} alt="" />
            <div>
              <strong>Cluster Assurance</strong>
              <span>Orchestrator for Nutanix Environments</span>
            </div>
          </button>
        </div>
        <nav>
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <div className="nav-group-label">{group.label}</div>
              <div className="nav-group-items">
                {group.itemIds.map((pageId) => {
                  const page = pages.find((candidate) => candidate.id === pageId);
                  if (!page) {
                    return null;
                  }
                  const Icon = page.icon;
                  return (
                    <button
                      key={page.id}
                      className={activePage === page.id ? "active" : ""}
                      type="button"
                      onClick={() => setActivePage(page.id)}
                    >
                      <Icon size={18} />
                      <span>{page.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span>Cluster Assurance Orchestrator {APP_VERSION_TAG}</span>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Cluster Assurance Orchestrator for Nutanix Environments</p>
            <h1>{activeMeta.label}</h1>
          </div>
          <div className="topbar-actions">
            <span className="mode-badge">Read-only lab evidence</span>
            {currentUser ? <span className="mode-badge">{currentUser.role_name}</span> : null}
            <button
              className="theme-toggle"
              type="button"
              onClick={() => setTheme((currentTheme) => currentTheme === "light" ? "dark" : "light")}
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
              title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
              <span>{theme === "light" ? "Dark" : "Light"}</span>
            </button>
            <button className="icon-button" type="button" onClick={() => void loadConsoleData()} aria-label="Refresh latest evidence">
              <RefreshCw size={16} />
            </button>
            <button className="theme-toggle" type="button" onClick={handleSignOut} aria-label="Sign out" title="Sign out">
              <LogOut size={16} />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        {STATIC_DEMO ? <Banner message="Public GitHub Pages demo: static read-only sample data. Docker or the appliance bundle is required for live Prism collection." /> : null}
        {error ? <Banner tone="unknown" message={error} /> : null}
        {loading ? <Banner message="Loading local assurance data..." /> : null}

        {activePage === "dashboard" ? (
          <DashboardPage
            run={run}
            problemCollectors={problemCollectors}
            schedule={schedule}
            readiness={readiness}
            support={supportStatus}
            history={healthRunHistory}
            onNavigate={setActivePage}
          />
        ) : null}
        {activePage === "triage" ? (
          <TriagePage
            run={run}
            problemCollectors={problemCollectors}
            schedule={schedule}
            readiness={readiness}
            support={supportStatus}
            history={healthRunHistory}
            onNavigate={setActivePage}
          />
        ) : null}
        {activePage === "estate" ? <EstatePage run={run} /> : null}
        {activePage === "runs" ? <RunsPage run={run} history={healthRunHistory} authToken={authToken} onRunComplete={loadConsoleData} /> : null}
        {activePage === "findings" ? <FindingsPage run={run} /> : null}
        {activePage === "schedules" ? <SchedulesPage schedule={schedule} authToken={authToken} onRunComplete={loadConsoleData} /> : null}
        {activePage === "evidence" ? <EvidencePage run={run} manifest={manifest} retention={retention} support={supportStatus} authToken={authToken} onRefresh={loadConsoleData} /> : null}
        {activePage === "settings" ? (
          <SettingsPage
            integrations={integrations}
            alerts={alerts}
            nccProfiles={nccProfiles}
            nccPlan={nccPlan}
            readiness={readiness}
            catalogue={catalogue}
            authToken={authToken}
            support={supportStatus}
            currentUser={currentUser}
            onAuthExpired={expireSession}
          />
        ) : null}
      </section>
    </main>
  );
}

function LoginPage(props: { onSignIn: (username: string, password: string) => Promise<string | null> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signingIn, setSigningIn] = useState(false);

  async function submitLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim() || !password) {
      setError("Enter a username and password.");
      return;
    }
    setError(null);
    setSigningIn(true);
    const signInError = await props.onSignIn(username.trim(), password);
    setSigningIn(false);
    if (signInError) {
      setError(signInError);
    }
  }

  return (
    <main className="login-page">
      <div className="login-shell">
        <section className="login-card" aria-labelledby="login-title">
          <div className="login-brand">
            <img src={`${ASSET_BASE}zto-logo-mark.svg`} alt="" width="72" height="72" />
            <div>
              <div className="login-product">Cluster Assurance</div>
              <div className="login-tagline">Orchestrator for Nutanix Environments</div>
            </div>
          </div>

          <form className="login-form" onSubmit={submitLogin}>
            <div className="login-intro">
              <h1 id="login-title">Sign in</h1>
              <p>Access your assurance workspace.</p>
            </div>

            <label className="login-field">
              <span>Username</span>
              <span className="login-input-wrap">
                <input
                  autoComplete="username"
                  autoFocus
                  className="login-input"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </span>
            </label>

            <label className="login-field">
              <span>Password</span>
              <span className="login-input-wrap">
                <input
                  autoComplete="current-password"
                  className="login-input login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="login-password-toggle"
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? <EyeOff size={23} /> : <Eye size={23} />}
                </button>
              </span>
            </label>

            {error ? <div className="login-error" role="alert">{error}</div> : null}

            <button className="login-submit" type="submit" disabled={signingIn}>
              {signingIn ? "Signing in..." : "Sign in"}
            </button>
          </form>

          <div className="login-help">Need access? Contact your administrator.</div>
        </section>

        <footer className="login-footer">
          <span>Cluster Assurance</span>
          <span aria-hidden="true">|</span>
          <a href="#documentation">Documentation</a>
        </footer>
      </div>
    </main>
  );
}

function DashboardPage(props: {
  run: InventoryRun | null;
  problemCollectors: Collector[];
  schedule: SchedulePreview | null;
  readiness: SecurityReadinessReport | null;
  support: SupportStatus | null;
  history: HealthRunHistoryItem[];
  onNavigate: (page: PageId) => void;
}) {
  const blockedGates = props.readiness?.gates.filter((gate) => gate.status !== "PASS").length ?? 0;
  const estateStatus = props.run?.status ?? "UNKNOWN";
  const primaryIssue = props.problemCollectors[0] ?? null;
  const failedCollectors = props.problemCollectors;
  const healthyCollectors = props.run?.collectors.filter((collector) => collector.status === "HEALTHY") ?? [];
  const confidence = evidenceConfidence(props.support);
  const changes = runChangeSummary(props.history);
  const nextRun = props.schedule?.occurrences[0];
  const domains = operationalDomains(props.run, props.support);
  return (
    <>
      <section className="ops-strip" aria-label="Operations overview">
        <OpsStripItem label="Estate Health" status={estateStatus} value={estateStatus} detail={props.run ? `${props.run.clusters.length} observed cluster(s)` : "No evidence"} />
        <OpsStripItem label="Collection" status={failedCollectors.length ? "WARNING" : "HEALTHY"} value={`${healthyCollectors.length}/${props.run?.collectors.length ?? 0}`} detail={`${failedCollectors.length} collector issue(s)`} />
        <OpsStripItem label="Readiness" status={blockedGates ? "WARNING" : "HEALTHY"} value={blockedGates ? `${blockedGates} open` : "Clear"} detail="Production gate posture" />
        <OpsStripItem label="Schedule" status={nextRun?.status === "ready" ? "HEALTHY" : "WARNING"} value={nextRun ? formatDate(nextRun.occurrence_at) : "None"} detail={nextRun?.reason ?? "No preview"} />
        <OpsStripItem label="Evidence Trust" status={confidence.status} value={confidence.label} detail={confidence.detail} />
      </section>
      <section className={`ops-hero ${estateStatus.toLowerCase()}`} aria-label="Operational summary">
        <div className="ops-hero-main">
          <div className="ops-kicker">Current estate verdict</div>
          <h2>{estateStatus}</h2>
          <p>{dashboardReason(primaryIssue, props.support)}</p>
          <div className="ops-chip-row">
            <span className={`status ${estateStatus.toLowerCase()}`}>{estateStatus}</span>
            <span className="ops-chip">{props.support?.mode.demo_mode ? "Demo mode" : props.support?.mode.environment ?? "Mode unknown"}</span>
            <span className="ops-chip">{confidence.label}</span>
            <span className="ops-chip">Last run {props.support?.latest_run.age_seconds != null ? formatAge(props.support.latest_run.age_seconds) : "unknown"}</span>
            <span className="ops-chip">{changes}</span>
          </div>
        </div>
        <div className="ops-next-actions">
          <button className="primary-button" type="button" onClick={() => props.onNavigate("runs")}>
            <Activity size={16} />
            Run health check
          </button>
          <button className="secondary-button" type="button" onClick={() => props.onNavigate("settings")}>
            <Network size={16} />
            Test connection
          </button>
          <button className="secondary-button" type="button" onClick={() => props.onNavigate("triage")}>
            <ArrowRight size={16} />
            Open triage
          </button>
          <button className="secondary-button" type="button" onClick={() => props.onNavigate("evidence")}>
            <FileJson size={16} />
            Open evidence
          </button>
        </div>
      </section>

      <section className="ops-card-grid" aria-label="Operational cards">
        <OperatorCard
          icon={<AlertTriangle />}
          title="Current Health"
          status={estateStatus}
          summary={primaryIssue ? primaryIssue.summary : "No failing collectors are recorded for the latest run."}
          action="Open health runs"
          onAction={() => props.onNavigate("runs")}
        />
        <OperatorCard
          icon={<Database />}
          title="Collection Coverage"
          status={failedCollectors.length ? "WARNING" : "HEALTHY"}
          summary={`${props.run?.clusters.length ?? 0} cluster(s), ${healthyCollectors.length} healthy collector(s), ${failedCollectors.length} issue(s).`}
          action="View estate"
          onAction={() => props.onNavigate("estate")}
        />
        <OperatorCard
          icon={<CalendarClock />}
          title="Schedule Status"
          status={nextRun?.status === "ready" ? "HEALTHY" : nextRun?.status === "partial" ? "WARNING" : "UNKNOWN"}
          summary={nextRun ? `${props.schedule?.schedule.name}: ${formatDate(nextRun.occurrence_at)}` : "No schedule preview is available."}
          action="Manage schedules"
          onAction={() => props.onNavigate("schedules")}
        />
        <OperatorCard
          icon={<ShieldCheck />}
          title="Readiness Gates"
          status={blockedGates ? "WARNING" : "HEALTHY"}
          summary={`${blockedGates} gate(s) still need attention before production claims.`}
          action="Review gates"
          onAction={() => props.onNavigate("settings")}
        />
      </section>

      <DomainHealthGrid
        title="Operational Domains"
        description="Support engineers expect these views for Nutanix operations. Current evidence covers inventory; storage, hardware, network and capacity need dedicated collectors before they can be trusted."
        domains={domains}
        onNavigate={props.onNavigate}
      />

      <section className="panel">
        <PanelHeading title="Collector Attention" description="Issues first, with likely operator action before supporting detail." />
        <div className="collector-focus-list">
          {failedCollectors.map((collector) => (
            <article className="collector-focus" key={`${collector.endpoint_alias}-${collector.path}`}>
              <div>
                <strong>{collectorTitle(collector)}</strong>
                <p>{collector.summary}</p>
                <small>{collector.method} {collector.path} · HTTP {collector.status_code ?? "-"}</small>
              </div>
              <span className={`status ${collector.status.toLowerCase()}`}>{collector.status}</span>
            </article>
          ))}
          {!failedCollectors.length ? <div className="empty-state">No failing collectors are recorded for the latest run.</div> : null}
        </div>
        {healthyCollectors.length ? (
          <div className="healthy-collector-strip">
            <span>{healthyCollectors.length} healthy collector(s)</span>
            {healthyCollectors.slice(0, 3).map((collector) => <span key={`${collector.endpoint_alias}-${collector.path}`}>{collector.endpoint_alias}</span>)}
          </div>
        ) : null}
      </section>

      <section className="panel two-column">
        <div>
          <PanelHeading title="Next Scheduled Work" description="Calculated locally with idempotency keys and lock awareness." />
          <dl className="details-grid compact">
            <div><dt>Schedule</dt><dd>{props.schedule?.schedule.name ?? "-"}</dd></div>
            <div><dt>Next Run</dt><dd>{nextRun ? formatDate(nextRun.occurrence_at) : "-"}</dd></div>
            <div><dt>Locks</dt><dd>{props.schedule?.active_locks.length ?? 0}</dd></div>
            <div><dt>Targets</dt><dd>{props.schedule?.schedule.target_cluster_ids.length ?? 0}</dd></div>
          </dl>
        </div>
        <div>
          <PanelHeading title="Readiness" description="Production claims stay blocked until gates are closed." />
          <ul className="event-list">
            {(props.readiness?.gates ?? []).slice(0, 4).map((gate) => (
              <li key={gate.gate_id}><StatusBadge status={gateTone(gate.status)} /> {gate.name}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="panel diagnostics-panel">
        <PanelHeading title="Support Diagnostics" description="Compact runtime context for handover and evidence trust." />
        {props.support?.warnings.length ? <Banner tone="warning" message={props.support.warnings[0]} /> : null}
        <dl className="details-grid">
          <div><dt>Mode</dt><dd>{props.support ? `${props.support.mode.environment}${props.support.mode.demo_mode ? " / demo" : ""}` : "-"}</dd></div>
          <div><dt>API URL</dt><dd>{props.support?.api_url ?? "-"}</dd></div>
          <div><dt>Config source</dt><dd>{props.support?.config_source ?? "-"}</dd></div>
          <div><dt>Evidence storage</dt><dd>{props.support?.evidence_directory ? "Configured locally" : "-"}</dd></div>
          <div><dt>Settings DB</dt><dd>{props.support?.admin_database ?? "-"}</dd></div>
          <div><dt>Last run type</dt><dd>{props.support?.latest_run.run_type ?? "-"}</dd></div>
          <div><dt>TLS mode</dt><dd>{props.support?.mode.tls_mode ?? "-"}</dd></div>
        </dl>
      </section>
    </>
  );
}

function TriagePage(props: {
  run: InventoryRun | null;
  problemCollectors: Collector[];
  schedule: SchedulePreview | null;
  readiness: SecurityReadinessReport | null;
  support: SupportStatus | null;
  history: HealthRunHistoryItem[];
  onNavigate: (page: PageId) => void;
}) {
  const confidence = evidenceConfidence(props.support);
  const lastRun = props.history[0] ?? null;
  const previousRun = props.history[1] ?? null;
  const openGates = props.readiness?.gates.filter((gate) => gate.status !== "PASS") ?? [];
  const nextRun = props.schedule?.occurrences[0] ?? null;
  const domains = operationalDomains(props.run, props.support);
  const primaryAction = props.problemCollectors.length ? "Fix the failing collector, then rerun health collection." : openGates.length ? "Review open readiness gates before production claims." : "Export evidence or keep monitoring scheduled health checks.";
  return (
    <>
      <section className="triage-hero">
        <div>
          <p className="eyebrow">Operator Triage</p>
          <h2>{props.run?.status ?? "UNKNOWN"}</h2>
          <p>{primaryAction}</p>
        </div>
        <div className="triage-actions">
          <button className="primary-button" type="button" onClick={() => props.onNavigate("runs")}><Activity size={16} />Run / inspect</button>
          <button className="secondary-button" type="button" onClick={() => props.onNavigate("settings")}><Network size={16} />Connections</button>
          <button className="secondary-button" type="button" onClick={() => props.onNavigate("evidence")}><FileJson size={16} />Evidence</button>
        </div>
      </section>
      <section className="triage-grid">
        <TriageStep number="1" title="Is the estate healthy?" status={props.run?.status ?? "UNKNOWN"} detail={props.problemCollectors.length ? `${props.problemCollectors.length} collector issue(s) require attention.` : "No failing collectors are recorded."} action="Open health runs" onAction={() => props.onNavigate("runs")} />
        <TriageStep number="2" title="Is the data fresh?" status={lastRun?.age_seconds != null && lastRun.age_seconds < 24 * 60 * 60 ? "HEALTHY" : "WARNING"} detail={lastRun?.age_seconds != null ? `Latest run is ${formatAge(lastRun.age_seconds)} old.` : "No run history is available."} action="Review evidence" onAction={() => props.onNavigate("evidence")} />
        <TriageStep number="3" title="Which collector failed?" status={props.problemCollectors.length ? "WARNING" : "HEALTHY"} detail={props.problemCollectors[0]?.summary ?? "All latest collectors are healthy."} action="Open details" onAction={() => props.onNavigate("runs")} />
        <TriageStep number="4" title="What changed?" status={runChangeStatus(lastRun, previousRun)} detail={runChangeSummary(props.history)} action="View timeline" onAction={() => props.onNavigate("runs")} />
        <TriageStep number="5" title="What should I do next?" status={props.problemCollectors.length || openGates.length ? "WARNING" : "HEALTHY"} detail={primaryAction} action={props.problemCollectors.length ? "Fix connection" : "Review gates"} onAction={() => props.onNavigate(props.problemCollectors.length ? "settings" : "settings")} />
        <TriageStep number="6" title="Where is the evidence?" status={confidence.status} detail={`${confidence.label}: ${confidence.detail}`} action="Open evidence" onAction={() => props.onNavigate("evidence")} />
      </section>
      <DomainHealthGrid
        title="Domain Coverage"
        description="This separates real collected evidence from the next monitoring areas operations will expect."
        domains={domains}
        onNavigate={props.onNavigate}
      />
      <section className="panel two-column">
        <div>
          <PanelHeading title="Immediate Attention" description="Only the items an operator should act on first." />
          <div className="attention-list">
            {props.problemCollectors.map((collector) => (
              <article className="attention-item" key={`${collector.endpoint_alias}-${collector.path}`}>
                <StatusBadge status={collector.status} />
                <div><strong>{collectorTitle(collector)}</strong><p>{collector.summary}</p><small>{collector.method} {collector.path} · HTTP {collector.status_code ?? "-"}</small></div>
              </article>
            ))}
            {!props.problemCollectors.length && openGates.slice(0, 3).map((gate) => (
              <article className="attention-item" key={gate.gate_id}>
                <StatusBadge status={gateTone(gate.status)} />
                <div><strong>{gate.name}</strong><p>{gate.summary}</p><small>{gate.evidence.join(", ")}</small></div>
              </article>
            ))}
            {!props.problemCollectors.length && !openGates.length ? <div className="empty-state">No urgent operator actions are open.</div> : null}
          </div>
        </div>
        <div>
          <PanelHeading title="Run Timeline" description="Recent run outcomes and schedule context." />
          <div className="timeline">
            {props.history.slice(0, 5).map((item) => (
              <div className="timeline-item" key={`${item.run_id}-${item.generated_at}`}>
                <Clock3 size={16} />
                <div><strong>{item.status}</strong><p>{item.generated_at ? formatDate(item.generated_at) : "Unknown time"} · {item.cluster_count} cluster(s), {item.collector_failure_count} issue(s)</p></div>
              </div>
            ))}
            {!props.history.length ? <div className="empty-state">No run timeline is available.</div> : null}
          </div>
          <Banner message={nextRun ? `Next scheduled work: ${formatDate(nextRun.occurrence_at)} (${nextRun.status}).` : "No scheduled work preview is available."} />
        </div>
      </section>
    </>
  );
}

function EstatePage(props: { run: InventoryRun | null }) {
  const clusters = props.run?.clusters ?? [];
  const prismSources = new Set(clusters.map((cluster) => cluster.source)).size;
  const versions = new Set(clusters.map((cluster) => cluster.version).filter(Boolean)).size;
  const collectedAges = clusters
    .map((cluster) => Math.max(0, Math.round((Date.now() - new Date(cluster.collected_at).getTime()) / 1000)))
    .filter((age) => Number.isFinite(age));
  const newestAge = collectedAges.length ? Math.min(...collectedAges) : null;
  return (
    <>
      <section className="visual-summary-grid">
        <Metric icon={<Database size={22} />} label="Observed Clusters" value={clusters.length.toString()} tone={clusters.length ? "" : "unknown"} />
        <Metric icon={<Network size={22} />} label="Prism Sources" value={prismSources.toString()} tone={prismSources ? "" : "unknown"} />
        <Metric icon={<History size={22} />} label="AOS Versions" value={versions.toString()} tone={versions > 1 ? "warning" : ""} />
        <Metric icon={<Clock3 size={22} />} label="Newest Evidence" value={newestAge != null ? formatAge(newestAge) : "No evidence"} tone={newestAge == null ? "unknown" : ""} />
      </section>
      <section className="panel">
        <PanelHeading title="Cluster Estate Map" description="At-a-glance cluster cards first, with normalized raw-evidence details below." />
        <div className="cluster-card-grid">
          {clusters.map((cluster) => (
            <article className="cluster-card" key={`${cluster.source}-${cluster.external_id}`}>
              <div className="cluster-card-top">
                <Database size={20} />
                <StatusBadge status={cluster.state?.toLowerCase() === "complete" ? "HEALTHY" : "UNKNOWN"} />
              </div>
              <h3>{cluster.name}</h3>
              <p>{labelize(cluster.source)} · {cluster.version ?? "Version unknown"}</p>
              <dl>
                <div><dt>State</dt><dd>{cluster.state ?? "-"}</dd></div>
                <div><dt>Collected</dt><dd>{formatDate(cluster.collected_at)}</dd></div>
                <div><dt>Artifact</dt><dd className="mono">{truncate(cluster.raw_artifact_sha256)}</dd></div>
              </dl>
            </article>
          ))}
          {!clusters.length ? <div className="empty-state">No normalized clusters are available.</div> : null}
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Cluster Evidence Detail" description="Normalized from raw Prism payloads and linked back to artifact hashes." />
        <DataTable
          columns={["Cluster", "Source", "Version", "State", "Collected"]}
          rows={clusters.map((cluster) => [
            <span className="stacked"><strong>{cluster.name}</strong><small>{cluster.external_id}</small></span>,
            labelize(cluster.source),
            cluster.version ?? "-",
            cluster.state ?? "-",
            formatDate(cluster.collected_at)
          ])}
          emptyText="No normalized clusters are available."
        />
      </section>
    </>
  );
}

function RunsPage(props: { run: InventoryRun | null; history: HealthRunHistoryItem[]; authToken: string; onRunComplete: () => void | Promise<void> }) {
  const [manualRunMessage, setManualRunMessage] = useState<string | null>(null);
  const [manualRunBusy, setManualRunBusy] = useState(false);
  const [collectorFilter, setCollectorFilter] = useState<"all" | "failed">("all");
  const visibleCollectors = collectorFilter === "failed"
    ? props.run?.collectors.filter((collector) => collector.status !== "HEALTHY") ?? []
    : props.run?.collectors ?? [];
  const collectorCount = props.run?.collectors.length ?? 0;
  const healthyCollectors = props.run?.collectors.filter((collector) => collector.status === "HEALTHY").length ?? 0;
  const latestHistory = props.history[0] ?? null;

  async function startManualRun() {
    setManualRunBusy(true);
    setManualRunMessage(null);
    try {
      const result = await fetchJson<{ run_id: string; status: HealthStatus; evidence_path: string }>(
        "/api/v1/health-runs/manual",
        { method: "POST" },
        props.authToken
      );
      setManualRunMessage(`Started run ${result.run_id} with status ${result.status}.`);
      await props.onRunComplete();
    } catch (runError) {
      setManualRunMessage(runError instanceof Error ? runError.message : "Unable to start health run.");
    } finally {
      setManualRunBusy(false);
    }
  }

  return (
    <>
      <section className="panel">
        <PanelHeading title="Manual Health Check" description="Start a read-only health collection immediately and write evidence locally." />
        <div className="toolbar">
          <button className="primary-button" type="button" onClick={startManualRun} disabled={manualRunBusy}>
            <Activity size={16} />
            {manualRunBusy ? "Starting..." : "Start health check"}
          </button>
          {manualRunMessage ? <span className="inline-message">{manualRunMessage}</span> : null}
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Run Details" description="Latest local inventory evidence with collector timing, endpoint and remediation context." />
        <div className="run-visual-grid">
          <RunVisualCard label="Latest Verdict" value={props.run?.status ?? "UNKNOWN"} status={props.run?.status ?? "UNKNOWN"} detail={props.run ? formatDate(props.run.generated_at) : "No run available"} />
          <RunVisualCard label="Collector Coverage" value={`${healthyCollectors}/${collectorCount}`} status={collectorCount && healthyCollectors === collectorCount ? "HEALTHY" : "WARNING"} detail={`${collectorCount - healthyCollectors} issue(s)`} />
          <RunVisualCard label="Clusters Covered" value={`${props.run?.clusters.length ?? 0}`} status={props.run?.clusters.length ? "HEALTHY" : "UNKNOWN"} detail="Inventory evidence only" />
          <RunVisualCard label="Last Run Age" value={latestHistory?.age_seconds != null ? formatAge(latestHistory.age_seconds) : "-"} status={latestHistory?.age_seconds != null && latestHistory.age_seconds < 24 * 60 * 60 ? "HEALTHY" : "WARNING"} detail={latestHistory?.run_type ?? "No history"} />
        </div>
        <dl className="details-grid">
          <div><dt>Run ID</dt><dd>{props.run?.run_id ?? "-"}</dd></div>
          <div><dt>Generated</dt><dd>{props.run ? formatDate(props.run.generated_at) : "-"}</dd></div>
          <div><dt>Maturity</dt><dd>{props.run?.maturity ?? "-"}</dd></div>
          <div><dt>Read only</dt><dd>{props.run?.read_only ? "Yes" : "No"}</dd></div>
          <div><dt>NCC enabled</dt><dd>{props.run?.ncc_enabled ? "Yes" : "No"}</dd></div>
          <div><dt>SSH enabled</dt><dd>{props.run?.ssh_enabled ? "Yes" : "No"}</dd></div>
        </dl>
        <div className="toolbar">
          <button className={collectorFilter === "all" ? "primary-button" : "secondary-button"} type="button" onClick={() => setCollectorFilter("all")}><Filter size={16} />All collectors</button>
          <button className={collectorFilter === "failed" ? "primary-button" : "secondary-button"} type="button" onClick={() => setCollectorFilter("failed")}><AlertTriangle size={16} />Failures only</button>
        </div>
        <div className="collector-matrix">
          {visibleCollectors.map((collector) => (
            <article className={`collector-tile ${collector.status.toLowerCase()}`} key={`${collector.endpoint_alias}-${collector.path}`}>
              <div><strong>{collector.endpoint_alias}</strong><small>{collector.method} {collector.path}</small></div>
              <StatusBadge status={collector.status} />
              <div className="mini-meter"><span style={{ width: `${collector.status === "HEALTHY" ? 100 : 35}%` }} /></div>
              <p>{collector.summary}</p>
            </article>
          ))}
        </div>
        <CollectorTable collectors={visibleCollectors} />
      </section>
      <section className="panel">
        <PanelHeading title="Run History" description="Recent health evidence with age, collector failures and local evidence paths." />
        <div className="run-timeline-grid">
          {props.history.slice(0, 4).map((item) => (
            <article className={`history-card ${item.status.toLowerCase()}`} key={`${item.run_id}-${item.generated_at}`}>
              <StatusBadge status={item.status} />
              <strong>{item.generated_at ? formatDate(item.generated_at) : "Unknown time"}</strong>
              <span>{item.cluster_count} cluster(s) · {item.collector_count} collector(s)</span>
              <small>{item.collector_failure_count ? `${item.collector_failure_count} issue(s)` : "No collector issues"}</small>
            </article>
          ))}
        </div>
        <DataTable
          columns={["Generated", "Status", "Coverage", "Failures", "Evidence"]}
          rows={props.history.map((item) => [
            item.generated_at ? formatDate(item.generated_at) : "-",
            <StatusBadge status={item.status} />,
            `${item.cluster_count} cluster(s), ${item.collector_count} collector(s)`,
            item.collector_failure_count ? `${item.collector_failure_count} issue(s)` : "None",
            item.path ? <span className="mono">{safePathLabel(item.path)}</span> : "-"
          ])}
          emptyText="No run history is available."
        />
      </section>
    </>
  );
}

function FindingsPage(props: { run: InventoryRun | null }) {
  const [filter, setFilter] = useState<"all" | HealthStatus>("all");
  const observations = props.run?.observations ?? [];
  const visibleObservations = filter === "all" ? observations : observations.filter((observation) => observation.status === filter);
  const severities: HealthStatus[] = ["CRITICAL", "WARNING", "UNKNOWN", "HEALTHY"];
  return (
    <section className="panel">
      <PanelHeading title="Findings" description="Severity-grouped observations from the latest run, with filters for support triage." />
      <div className="severity-grid">
        {severities.map((severity) => {
          const count = observations.filter((observation) => observation.status === severity).length;
          return (
            <button className={`severity-card ${severity.toLowerCase()} ${filter === severity ? "active" : ""}`} type="button" onClick={() => setFilter(severity)} key={severity}>
              <StatusBadge status={severity} />
              <strong>{count}</strong>
              <span>{labelize(severity.toLowerCase())}</span>
            </button>
          );
        })}
      </div>
      <div className="toolbar">
        <button className={filter === "all" ? "primary-button" : "secondary-button"} type="button" onClick={() => setFilter("all")}>All</button>
        {severities.map((severity) => (
          <button className={filter === severity ? "primary-button" : "secondary-button"} type="button" onClick={() => setFilter(severity)} key={severity}>
            {severity} ({observations.filter((observation) => observation.status === severity).length})
          </button>
        ))}
      </div>
      <DataTable
        columns={["Check", "Status", "Source", "Summary"]}
        rows={visibleObservations.map((observation) => [
          observation.check_id,
          <StatusBadge status={observation.status} />,
          labelize(observation.source),
          observation.summary
        ])}
        emptyText="No observations are available."
      />
    </section>
  );
}

function SchedulesPage(props: { schedule: SchedulePreview | null; authToken: string; onRunComplete: () => void | Promise<void> }) {
  const [schedules, setSchedules] = useState<ManagedSchedule[]>([]);
  const [runHistory, setRunHistory] = useState<ScheduleRunHistory[]>([]);
  const [scheduleMessage, setScheduleMessage] = useState<string | null>(null);
  const [runnerBusy, setRunnerBusy] = useState(false);
  const [draft, setDraft] = useState({
    scheduleId: "",
    name: "",
    recurrence: "daily" as ManagedSchedule["definition"]["recurrence"],
    startTime: "06:00",
    timezone: "Europe/Berlin",
    weeklyDay: 0,
    targetClusterIds: ""
  });
  const enabledSchedules = schedules.filter((schedule) => schedule.enabled).length;
  const nextOccurrence = props.schedule?.occurrences[0] ?? null;
  const blockedTargets = nextOccurrence?.blocked_cluster_ids.length ?? 0;
  const lastScheduledRun = runHistory[0] ?? null;

  useEffect(() => {
    void loadSchedules();
  }, [props.authToken]);

  async function loadSchedules() {
    try {
      const [scheduleRows, historyRows] = await Promise.all([
        fetchJson<ManagedSchedule[]>("/api/v1/schedules", {}, props.authToken),
        fetchJson<ScheduleRunHistory[]>("/api/v1/schedules/runs/history", {}, props.authToken)
      ]);
      setSchedules(scheduleRows);
      setRunHistory(historyRows);
    } catch (scheduleError) {
      setScheduleMessage(scheduleError instanceof Error ? scheduleError.message : "Unable to load schedules.");
    }
  }

  async function createSchedule() {
    if (!draft.name.trim()) {
      return;
    }
    const scheduleId = draft.scheduleId.trim() || draft.name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    await fetchJson<ManagedSchedule>("/api/v1/schedules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildScheduleRequest({
        schedule_id: scheduleId,
        name: draft.name,
        recurrence: draft.recurrence,
        start_time: draft.startTime,
        timezone: draft.timezone,
        weekly_day: draft.weeklyDay,
        target_cluster_ids: splitTargets(draft.targetClusterIds),
        enabled: true
      }))
    }, props.authToken);
    setDraft({ scheduleId: "", name: "", recurrence: "daily", startTime: "06:00", timezone: "Europe/Berlin", weeklyDay: 0, targetClusterIds: "" });
    setScheduleMessage("Schedule created.");
    await loadSchedules();
  }

  async function saveSchedule(schedule: ManagedSchedule) {
    await fetchJson<ManagedSchedule>(`/api/v1/schedules/${schedule.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildScheduleRequest(schedule.definition))
    }, props.authToken);
    setScheduleMessage("Schedule updated.");
    await loadSchedules();
  }

  async function deleteSchedule(scheduleId: string) {
    await fetchJson<{ status: string }>(`/api/v1/schedules/${scheduleId}`, { method: "DELETE" }, props.authToken);
    setScheduleMessage("Schedule deleted.");
    await loadSchedules();
  }

  async function runDueSchedules() {
    setRunnerBusy(true);
    try {
      const result = await fetchJson<{ due_schedules: number }>("/api/v1/schedules/run-due", { method: "POST" }, props.authToken);
      setScheduleMessage(`Schedule runner checked due work: ${result.due_schedules} due schedule(s).`);
      await loadSchedules();
      await props.onRunComplete();
    } catch (runError) {
      setScheduleMessage(runError instanceof Error ? runError.message : "Unable to run due schedules.");
    } finally {
      setRunnerBusy(false);
    }
  }

  async function runScheduleNow(scheduleId: string) {
    setRunnerBusy(true);
    try {
      const result = await fetchJson<ScheduleRunHistory>(`/api/v1/schedules/${scheduleId}/run-now`, { method: "POST" }, props.authToken);
      setScheduleMessage(`Started ${scheduleId}: ${result.status}.`);
      await loadSchedules();
      await props.onRunComplete();
    } catch (runError) {
      setScheduleMessage(runError instanceof Error ? runError.message : "Unable to run schedule.");
    } finally {
      setRunnerBusy(false);
    }
  }

  function updateSchedule(scheduleId: string, updater: (schedule: ManagedSchedule) => ManagedSchedule) {
    setSchedules((current) => current.map((schedule) => schedule.id === scheduleId ? updater(schedule) : schedule));
  }

  return (
    <>
      <section className="panel">
        <PanelHeading title="Scheduled Health Checks" description="Create, modify or delete recurring read-only health checks." />
        {scheduleMessage ? <Banner message={scheduleMessage} /> : null}
        <div className="schedule-ops-grid">
          <RunVisualCard label="Configured" value={schedules.length.toString()} status={schedules.length ? "HEALTHY" : "UNKNOWN"} detail={`${enabledSchedules} enabled`} />
          <RunVisualCard label="Next Due" value={nextOccurrence ? formatDate(nextOccurrence.occurrence_at) : "None"} status={nextOccurrence?.status === "ready" ? "HEALTHY" : "WARNING"} detail={nextOccurrence?.reason ?? "No preview"} />
          <RunVisualCard label="Blocked Targets" value={blockedTargets.toString()} status={blockedTargets ? "WARNING" : "HEALTHY"} detail="Lock / idempotency guard" />
          <RunVisualCard label="Last Scheduled Run" value={lastScheduledRun?.status ?? "-"} status={scheduleRunStatus(lastScheduledRun?.status)} detail={lastScheduledRun?.started_at ? formatDate(lastScheduledRun.started_at) : "No scheduled history"} />
        </div>
        <div className="toolbar">
          <button className="secondary-button" type="button" onClick={runDueSchedules} disabled={runnerBusy}>
            <RefreshCw size={16} />
            {runnerBusy ? "Checking..." : "Run due schedules"}
          </button>
        </div>
        <div className="form-grid schedule-form">
          <label><span>ID</span><input value={draft.scheduleId} onChange={(event) => setDraft((current) => ({ ...current, scheduleId: event.target.value }))} placeholder="daily-lab" /></label>
          <label><span>Name</span><input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} placeholder="Daily Lab Health" /></label>
          <label><span>Recurrence</span><select value={draft.recurrence} onChange={(event) => setDraft((current) => ({ ...current, recurrence: event.target.value as ManagedSchedule["definition"]["recurrence"] }))}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="on_demand">On demand</option></select></label>
          <label><span>Time</span><input value={draft.startTime} onChange={(event) => setDraft((current) => ({ ...current, startTime: event.target.value }))} type="time" /></label>
          <label><span>Timezone</span><input value={draft.timezone} onChange={(event) => setDraft((current) => ({ ...current, timezone: event.target.value }))} /></label>
          <label><span>Targets</span><input value={draft.targetClusterIds} onChange={(event) => setDraft((current) => ({ ...current, targetClusterIds: event.target.value }))} placeholder="cluster-a, cluster-b" /></label>
          <button className="primary-button" type="button" onClick={createSchedule}><Plus size={16} />Create schedule</button>
        </div>
        <div className="editable-list">
          {schedules.map((schedule) => (
            <div className="editable-row schedule-row" key={schedule.id}>
              <input value={schedule.definition.name} onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, definition: { ...item.definition, name: event.target.value }, name: event.target.value }))} aria-label={`${schedule.name} name`} />
              <select value={schedule.definition.recurrence} onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, definition: { ...item.definition, recurrence: event.target.value as ManagedSchedule["definition"]["recurrence"] } }))} aria-label={`${schedule.name} recurrence`}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="on_demand">On demand</option></select>
              <input value={schedule.definition.start_time} type="time" onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, definition: { ...item.definition, start_time: event.target.value } }))} aria-label={`${schedule.name} start time`} />
              <input value={schedule.definition.timezone} onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, definition: { ...item.definition, timezone: event.target.value } }))} aria-label={`${schedule.name} timezone`} />
              <input value={schedule.definition.target_cluster_ids.join(", ")} onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, definition: { ...item.definition, target_cluster_ids: splitTargets(event.target.value) } }))} aria-label={`${schedule.name} targets`} />
              <select value={schedule.definition.enabled ? "enabled" : "disabled"} onChange={(event) => updateSchedule(schedule.id, (item) => ({ ...item, enabled: event.target.value === "enabled", definition: { ...item.definition, enabled: event.target.value === "enabled" } }))} aria-label={`${schedule.name} enabled`}>
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
              <span className="row-actions">
                <button className="table-action" type="button" onClick={() => saveSchedule(schedule)}>Save</button>
                <button className="table-action" type="button" onClick={() => runScheduleNow(schedule.id)}>Run now</button>
                <button className="table-action danger" type="button" onClick={() => deleteSchedule(schedule.id)}><Trash2 size={14} />Delete</button>
              </span>
            </div>
          ))}
          {!schedules.length ? <div className="empty-state">No scheduled health checks are configured.</div> : null}
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Next Schedule Preview" description="Deterministic occurrences and idempotency keys. Locked clusters cannot start twice." />
        <dl className="details-grid">
          <div><dt>Schedule</dt><dd>{props.schedule?.schedule.name ?? "-"}</dd></div>
          <div><dt>Profile</dt><dd>{props.schedule ? `${props.schedule.schedule.profile.name} v${props.schedule.schedule.profile.version}` : "-"}</dd></div>
          <div><dt>Recurrence</dt><dd>{props.schedule ? `${props.schedule.schedule.recurrence} at ${props.schedule.schedule.start_time}` : "-"}</dd></div>
          <div><dt>Timezone</dt><dd>{props.schedule?.schedule.timezone ?? "-"}</dd></div>
        </dl>
        <DataTable
          columns={["Occurrence", "Status", "Runnable / blocked", "Idempotency key"]}
          rows={(props.schedule?.occurrences ?? []).map((occurrence) => [
            formatDate(occurrence.occurrence_at),
            <span className={`status ${scheduleStatusTone(occurrence.status)}`}>{occurrence.status.toUpperCase()}</span>,
            `${occurrence.runnable_cluster_ids.length} runnable / ${occurrence.blocked_cluster_ids.length} blocked`,
            <span className="mono">{truncate(occurrence.idempotency_key)}</span>
          ])}
          emptyText="No schedule preview is available."
        />
      </section>
      <section className="panel">
        <PanelHeading title="Schedule Run History" description="Persisted run attempts with idempotency and lock outcomes." />
        <DataTable
          columns={["Schedule", "Status", "Started", "Run ID", "Message"]}
          rows={runHistory.map((history) => [
            history.schedule_id,
            <span className={`status ${scheduleRunTone(history.status)}`}>{history.status}</span>,
            formatDate(history.started_at),
            history.run_id ? <span className="mono">{truncate(history.run_id)}</span> : "-",
            history.message
          ])}
          emptyText="No scheduled health check runs have been recorded."
        />
      </section>
    </>
  );
}

function EvidencePage(props: { run: InventoryRun | null; manifest: EvidenceManifest | null; retention: RetentionReport | null; support: SupportStatus | null; authToken: string; onRefresh: () => void | Promise<void> }) {
  const [evidenceMessage, setEvidenceMessage] = useState<string | null>(null);
  const confidence = evidenceConfidence(props.support);

  async function exportArchive() {
    const result = await fetchJson<{ archive_path: string; sha256: string }>("/api/v1/evidence/archive/export", { method: "POST" }, props.authToken);
    setEvidenceMessage(`Archive created: ${result.archive_path}`);
    await props.onRefresh();
  }

  async function runRestoreDrill() {
    const result = await fetchJson<{ status: string; artifact_count: number }>("/api/v1/evidence/restore-drill", { method: "POST" }, props.authToken);
    setEvidenceMessage(`Restore drill ${result.status}: ${result.artifact_count} artifact(s) checked.`);
    await props.onRefresh();
  }

  async function pruneRetention() {
    const result = await fetchJson<RetentionReport>("/api/v1/evidence/retention/prune", { method: "POST" }, props.authToken);
    setEvidenceMessage(`Retention prune deleted ${result.deleted_files?.length ?? 0} file(s).`);
    await props.onRefresh();
  }

  return (
    <>
      <section className="panel">
        <PanelHeading title="Evidence Confidence" description="Support-safe summary of whether the latest evidence is live, fresh, complete and production-trustworthy." />
        <div className="evidence-flow">
          <EvidenceStep icon={<Activity size={18} />} label="Collected" status={props.support?.latest_run.available ? "HEALTHY" : "UNKNOWN"} detail={props.support?.latest_run.run_type ?? "No run"} />
          <EvidenceStep icon={<FileJson size={18} />} label="Hashed" status={props.manifest?.manifest_sha256 ? "HEALTHY" : "UNKNOWN"} detail={props.manifest ? truncate(props.manifest.manifest_sha256) : "No manifest"} />
          <EvidenceStep icon={<History size={18} />} label="Retained" status={props.retention?.inventory_runs ? "HEALTHY" : "UNKNOWN"} detail={props.retention ? `${props.retention.inventory_runs} run(s)` : "Policy not loaded"} />
          <EvidenceStep icon={<ShieldCheck size={18} />} label="Trusted" status={confidence.status} detail={confidence.label} />
        </div>
        <dl className="details-grid">
          <div><dt>Confidence</dt><dd><StatusBadge status={confidence.status} /> {confidence.label}</dd></div>
          <div><dt>Latest run</dt><dd>{props.support?.latest_run.run_id ? truncate(props.support.latest_run.run_id) : "-"}</dd></div>
          <div><dt>Age</dt><dd>{props.support?.latest_run.age_seconds != null ? formatAge(props.support.latest_run.age_seconds) : "-"}</dd></div>
          <div><dt>Config source</dt><dd>{props.support?.config_source ?? "-"}</dd></div>
        </dl>
        {props.support?.warnings.map((warning) => <Banner key={warning} tone="warning" message={warning} />)}
      </section>
      <section className="panel">
        <PanelHeading title="Retention and Backup" description="Local evidence retention, archive export and restore-drill controls." />
        {evidenceMessage ? <Banner message={evidenceMessage} /> : null}
        <dl className="details-grid">
          <div><dt>Retention</dt><dd>{props.retention ? `${props.retention.policy.retention_days} days / keep ${props.retention.policy.minimum_runs}` : "-"}</dd></div>
          <div><dt>Inventory runs</dt><dd>{props.retention?.inventory_runs ?? "-"}</dd></div>
          <div><dt>Prunable</dt><dd>{props.retention?.deletable_runs ?? "-"}</dd></div>
          <div><dt>Evidence storage</dt><dd>{props.retention?.evidence_dir ? "Configured locally" : "-"}</dd></div>
        </dl>
        <div className="toolbar">
          <button className="secondary-button" type="button" onClick={exportArchive}>Export archive</button>
          <button className="secondary-button" type="button" onClick={runRestoreDrill}>Restore drill</button>
          <button className="table-action danger" type="button" onClick={pruneRetention}>Prune retention</button>
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Evidence Manifest" description="Local artifact hashes and manifest fingerprint without exposing raw payload contents." />
        <dl className="details-grid">
          <div><dt>Run ID</dt><dd>{props.manifest?.run_id ?? "-"}</dd></div>
          <div><dt>Product Version</dt><dd>{props.manifest?.product_version ?? "-"}</dd></div>
          <div><dt>Profile Version</dt><dd>{props.manifest?.profile_version ?? "-"}</dd></div>
          <div><dt>Manifest SHA-256</dt><dd className="mono">{props.manifest ? truncate(props.manifest.manifest_sha256) : "-"}</dd></div>
        </dl>
        <DataTable
          columns={["Artifact", "Reference", "SHA-256", "Size"]}
          rows={(props.manifest?.artifacts ?? []).map((artifact) => [
            labelize(artifact.artifact_type),
            safePathLabel(artifact.uri),
            <span className="mono">{truncate(artifact.sha256)}</span>,
            `${artifact.size_bytes} bytes`
          ])}
          emptyText="No manifest artifacts are available."
        />
      </section>
      <section className="panel">
        <PanelHeading title="Collector References" description="Raw artifact locations are local evidence references only." />
        <DataTable
          columns={["Collector", "Artifact", "SHA-256", "Size"]}
          rows={(props.run?.collectors ?? []).map((collector) => [
            collector.endpoint_alias,
            collector.raw_artifact?.uri ? safePathLabel(collector.raw_artifact.uri) : "-",
            collector.raw_artifact?.sha256 ? <span className="mono">{truncate(collector.raw_artifact.sha256)}</span> : "-",
            collector.raw_artifact ? `${collector.raw_artifact.size_bytes} bytes` : "-"
          ])}
          emptyText="No evidence artifacts are referenced."
        />
      </section>
    </>
  );
}

function SettingsPage(props: {
  integrations: IntegrationReport | null;
  alerts: AlertStatus | null;
  nccProfiles: NccProfilesResponse | null;
  nccPlan: NccPlan | null;
  readiness: SecurityReadinessReport | null;
  catalogue: CatalogueResponse | null;
  authToken: string;
  support: SupportStatus | null;
  currentUser: AuthUser | null;
  onAuthExpired: () => void;
}) {
  const [activeSettingsPage, setActiveSettingsPage] = useState<SettingsPageId>("storage");
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [connections, setConnections] = useState<ManagedConnection[]>([]);
  const [connectionDraft, setConnectionDraft] = useState({
    name: "",
    type: "Prism Central" as ManagedConnection["type"],
    url: "",
    username: "",
    password: "",
    tlsMode: "strict"
  });
  const [roles, setRoles] = useState<ManagedRole[]>([]);
  const [roleDraft, setRoleDraft] = useState({ name: "", permissions: "" });
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [storageStatus, setStorageStatus] = useState<StorageStatus | null>(null);
  const [userDraft, setUserDraft] = useState({
    username: "",
    name: "",
    email: "",
    roleId: "viewer",
    status: "Active" as ManagedUser["status"],
    password: ""
  });
  const [passwordDrafts, setPasswordDrafts] = useState<Record<string, string>>({});
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [selectedNccCheckIds, setSelectedNccCheckIds] = useState<string[]>([]);
  const [nccSelectionInitialized, setNccSelectionInitialized] = useState(false);

  useEffect(() => {
    void loadAdminState();
  }, [props.authToken]);

  useEffect(() => {
    if (!nccSelectionInitialized && props.catalogue?.checks.length) {
      setSelectedNccCheckIds(props.catalogue.checks.map((check) => check.check_id));
      setNccSelectionInitialized(true);
    }
  }, [nccSelectionInitialized, props.catalogue]);

  async function loadAdminState() {
    setSettingsError(null);
    if (STATIC_DEMO) {
      setRoles(demoRoles);
      setUsers(demoUsers);
      setConnections(demoConnections);
      setAuditEvents(demoAuditEvents);
      setStorageStatus(demoStorageStatus);
      return;
    }
    try {
      const [roleRows, userRows, connectionRows, auditRows, storageRows] = await Promise.all([
        fetchJson<Array<{ id: string; name: string; permissions: string[] }>>("/api/v1/rbac/roles", {}, props.authToken),
        fetchJson<Array<{
          id: string;
          username: string;
          name: string;
          email: string;
          role_id: string;
          role_name: string;
          status: ManagedUser["status"];
          password_set: boolean;
          password_updated_at: string | null;
        }>>("/api/v1/rbac/users", {}, props.authToken),
        fetchJson<Array<{
          id: string;
          name: string;
          type: ManagedConnection["type"];
          url: string;
          username: string;
          secret_set: boolean;
          tls_mode: string;
          status: string;
          last_checked_at: string | null;
        }>>("/api/v1/connections", {}, props.authToken),
        fetchJson<AuditEvent[]>("/api/v1/audit/events", {}, props.authToken),
        fetchJson<StorageStatus>("/api/v1/storage/status", {}, props.authToken)
      ]);
      setRoles(roleRows.map((role) => ({ id: role.id, name: role.name, permissions: role.permissions.join(", ") })));
      setUsers(userRows.map((user) => ({
        id: user.id,
        username: user.username,
        name: user.name,
        email: user.email,
        roleId: user.role_id,
        roleName: user.role_name,
        status: user.status,
        passwordSet: user.password_set,
        passwordUpdatedAt: user.password_updated_at
      })));
      setConnections(connectionRows.map((connection) => ({
        id: connection.id,
        name: connection.name,
        type: connection.type,
        url: connection.url,
        username: connection.username,
        secretSet: connection.secret_set,
        tlsMode: connection.tls_mode,
        status: connection.status,
        lastCheckedAt: connection.last_checked_at
      })));
      setAuditEvents(auditRows);
      setStorageStatus(storageRows);
    } catch (adminError) {
      if (isAuthError(adminError)) {
        props.onAuthExpired();
        return;
      }
      setSettingsError(adminError instanceof Error ? adminError.message : "Unable to load settings data.");
    }
  }

  async function createStorageBackup() {
    if (STATIC_DEMO) {
      setSettingsError("Backup creation is disabled in the static GitHub Pages demo.");
      return;
    }
    const backup = await fetchJson<DatabaseBackup>("/api/v1/storage/backups", { method: "POST" }, props.authToken);
    setSettingsError(`Created database backup ${backup.name}.`);
    await loadAdminState();
  }

  async function downloadStorageBackup(backupName: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Download is disabled for ${backupName} in the static GitHub Pages demo.`);
      return;
    }
    const blob = await fetchBlob(`/api/v1/storage/backups/${encodeURIComponent(backupName)}/download`, props.authToken);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = backupName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  async function showStorageBackupDetails(backupName: string) {
    if (STATIC_DEMO) {
      setSettingsError(`${backupName}: static demo backup metadata only.`);
      return;
    }
    const details = await fetchJson<DatabaseBackup & { storage: string }>(`/api/v1/storage/backups/${encodeURIComponent(backupName)}`, {}, props.authToken);
    setSettingsError(`${details.name}: ${details.size_label ?? formatBytes(details.size_bytes)} stored in ${details.storage}.`);
  }

  async function addConnection() {
    if (STATIC_DEMO) {
      setSettingsError("Connection changes are disabled in the static GitHub Pages demo.");
      return;
    }
    if (!connectionDraft.name.trim() || !connectionDraft.url.trim()) {
      return;
    }
    await fetchJson<ManagedConnection>("/api/v1/connections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: connectionDraft.name,
        type: connectionDraft.type,
        url: connectionDraft.url,
        username: connectionDraft.username,
        password: connectionDraft.password || null,
        tls_mode: connectionDraft.tlsMode
      })
    }, props.authToken);
    setConnectionDraft({ name: "", type: "Prism Central", url: "", username: "", password: "", tlsMode: "strict" });
    await loadAdminState();
  }

  async function deleteConnection(connectionId: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Connection deletion is disabled for ${connectionId} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<{ status: string }>(`/api/v1/connections/${connectionId}`, { method: "DELETE" }, props.authToken);
    await loadAdminState();
  }

  async function updateConnection(connection: ManagedConnection, password: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Connection updates are disabled for ${connection.name} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<ManagedConnection>(`/api/v1/connections/${connection.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: connection.name,
        type: connection.type,
        url: connection.url,
        username: connection.username,
        password: password || null,
        tls_mode: connection.tlsMode
      })
    }, props.authToken);
    await loadAdminState();
  }

  async function testConnection(connectionId: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Connection ${connectionId} is READY in static demo data. Docker is required for a real Prism probe.`);
      return;
    }
    await fetchJson<ManagedConnection>(`/api/v1/connections/${connectionId}/test`, { method: "POST" }, props.authToken);
    await loadAdminState();
  }

  async function addRole() {
    if (STATIC_DEMO) {
      setSettingsError("Role changes are disabled in the static GitHub Pages demo.");
      return;
    }
    if (!roleDraft.name.trim()) {
      return;
    }
    await fetchJson<ManagedRole>("/api/v1/rbac/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: roleDraft.name, permissions: permissionList(roleDraft.permissions || "view_dashboard") })
    }, props.authToken);
    setRoleDraft({ name: "", permissions: "" });
    await loadAdminState();
  }

  async function updateRole(role: ManagedRole) {
    if (STATIC_DEMO) {
      setSettingsError(`Role updates are disabled for ${role.name} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<ManagedRole>(`/api/v1/rbac/roles/${role.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: role.name, permissions: permissionList(role.permissions) })
    }, props.authToken);
    await loadAdminState();
  }

  async function deleteRole(roleId: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Role deletion is disabled for ${roleId} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<{ status: string }>(`/api/v1/rbac/roles/${roleId}`, { method: "DELETE" }, props.authToken);
    await loadAdminState();
  }

  async function addUser() {
    if (STATIC_DEMO) {
      setSettingsError("User changes are disabled in the static GitHub Pages demo.");
      return;
    }
    if (!userDraft.username.trim() || !userDraft.name.trim() || !userDraft.email.trim() || !userDraft.password.trim()) {
      return;
    }
    await fetchJson<ManagedUser>("/api/v1/rbac/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: userDraft.username,
        name: userDraft.name,
        email: userDraft.email,
        role_id: userDraft.roleId,
        status: userDraft.status,
        password: userDraft.password
      })
    }, props.authToken);
    setUserDraft({ username: "", name: "", email: "", roleId: roles[0]?.id ?? "viewer", status: "Active", password: "" });
    await loadAdminState();
  }

  async function updateUser(user: ManagedUser) {
    if (STATIC_DEMO) {
      setSettingsError(`User updates are disabled for ${user.username} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<ManagedUser>(`/api/v1/rbac/users/${user.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: user.username,
        name: user.name,
        email: user.email,
        role_id: user.roleId,
        status: user.status
      })
    }, props.authToken);
    await loadAdminState();
  }

  async function deleteUser(userId: string) {
    if (STATIC_DEMO) {
      setSettingsError(`User deletion is disabled for ${userId} in the static GitHub Pages demo.`);
      return;
    }
    await fetchJson<{ status: string }>(`/api/v1/rbac/users/${userId}`, { method: "DELETE" }, props.authToken);
    await loadAdminState();
  }

  async function setUserPassword(userId: string) {
    if (STATIC_DEMO) {
      setSettingsError(`Password changes are disabled for ${userId} in the static GitHub Pages demo.`);
      return;
    }
    const password = passwordDrafts[userId]?.trim();
    if (!password) {
      return;
    }
    await fetchJson<ManagedUser>(`/api/v1/rbac/users/${userId}/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password })
    }, props.authToken);
    setPasswordDrafts((current) => ({ ...current, [userId]: "" }));
    await loadAdminState();
  }

  const settingsPages: Array<{ id: SettingsPageId; label: string; icon: React.ComponentType<{ size?: number }> }> = [
    { id: "storage", label: "Storage", icon: Database },
    { id: "connections", label: "Connections", icon: Network },
    { id: "readiness", label: "Readiness Gates", icon: ShieldCheck },
    { id: "rbac", label: "RBAC Matrix", icon: Users },
    { id: "ncc", label: "NCC Gate", icon: ListChecks },
    { id: "audit", label: "Audit Log", icon: ClipboardList },
    { id: "about", label: "About", icon: ShieldCheck }
  ];

  return (
    <section className="settings-shell">
      <div className="settings-nav" aria-label="Settings sections">
        {settingsPages.map((page) => {
          const Icon = page.icon;
          return (
            <button
              key={page.id}
              className={activeSettingsPage === page.id ? "active" : ""}
              type="button"
              onClick={() => setActiveSettingsPage(page.id)}
            >
              <Icon size={16} />
              <span>{page.label}</span>
            </button>
          );
        })}
      </div>
      <div className="settings-overview-grid">
        <RunVisualCard label="Connections" value={connections.length.toString()} status={connections.some((connection) => connection.status === "READY") ? "HEALTHY" : "UNKNOWN"} detail={`${connections.filter((connection) => connection.status === "READY").length} ready`} />
        <RunVisualCard label="RBAC" value={`${users.length} user(s)`} status={users.length ? "HEALTHY" : "WARNING"} detail={`${roles.length} role(s) configured`} />
        <RunVisualCard label="NCC Gate" value={`${selectedNccCheckIds.length}`} status={props.nccPlan?.ncc_enabled ? "HEALTHY" : "UNKNOWN"} detail={props.nccPlan?.reason ?? "Execution gated"} />
        <RunVisualCard label="Audit" value={auditEvents.length.toString()} status={auditEvents.length ? "HEALTHY" : "UNKNOWN"} detail="Administrative event trail" />
      </div>
      {settingsError ? <Banner tone="unknown" message={settingsError} /> : null}

      {activeSettingsPage === "storage" ? (
        <StorageSettingsPage
          status={storageStatus}
          onRefresh={loadAdminState}
          onCreateBackup={createStorageBackup}
          onDownloadBackup={downloadStorageBackup}
          onBackupDetails={showStorageBackupDetails}
        />
      ) : null}
      {activeSettingsPage === "connections" ? (
        <ConnectionsPage
          report={props.integrations}
          alerts={props.alerts}
          connections={connections}
          draft={connectionDraft}
          setDraft={setConnectionDraft}
          onAdd={addConnection}
          onUpdate={updateConnection}
          onDelete={deleteConnection}
          onTest={testConnection}
        />
      ) : null}
      {activeSettingsPage === "readiness" ? <ReadinessPage report={props.readiness} /> : null}
      {activeSettingsPage === "rbac" ? (
        <RbacPage
          roles={roles}
          setRoles={setRoles}
          roleDraft={roleDraft}
          setRoleDraft={setRoleDraft}
          users={users}
          setUsers={setUsers}
          userDraft={userDraft}
          setUserDraft={setUserDraft}
          passwordDrafts={passwordDrafts}
          setPasswordDrafts={setPasswordDrafts}
          onAddRole={addRole}
          onAddUser={addUser}
          onSetPassword={setUserPassword}
          onUpdateUser={updateUser}
          onDeleteUser={deleteUser}
          onUpdateRole={updateRole}
          onDeleteRole={deleteRole}
        />
      ) : null}
      {activeSettingsPage === "ncc" ? (
        <NccSettingsPage
          profiles={props.nccProfiles}
          plan={props.nccPlan}
          catalogue={props.catalogue}
          selectedCheckIds={selectedNccCheckIds}
          setSelectedCheckIds={setSelectedNccCheckIds}
        />
      ) : null}
      {activeSettingsPage === "audit" ? <AuditEventsPage events={auditEvents} /> : null}
      {activeSettingsPage === "about" ? (
        <AboutPage
          support={props.support}
          currentUser={props.currentUser}
          connections={connections}
          roles={roles}
          users={users}
        />
      ) : null}
    </section>
  );
}

function StorageSettingsPage(props: {
  status: StorageStatus | null;
  onRefresh: () => void | Promise<void>;
  onCreateBackup: () => void | Promise<void>;
  onDownloadBackup: (backupName: string) => void | Promise<void>;
  onBackupDetails: (backupName: string) => void | Promise<void>;
}) {
  const backupSupported = props.status?.backup_supported ?? false;
  return (
    <section className="storage-settings">
      <div className="storage-settings-grid">
        <article className="panel storage-card">
          <div className="storage-card-heading">
            <div className="storage-card-icon"><Database size={18} /></div>
            <div>
              <h2>Storage Backend</h2>
              <p>Current persistence mode and state location</p>
            </div>
          </div>
          <dl className="storage-fields">
            <div><dt>Backend</dt><dd>{props.status?.backend ?? "-"}</dd></div>
            <div><dt>Status</dt><dd>{props.status?.status ?? "-"}</dd></div>
            <div><dt>Data Directory</dt><dd>{props.status?.data_directory ?? "-"}</dd></div>
            <div><dt>Database Location</dt><dd className="mono">{props.status?.database_location ?? "-"}</dd></div>
          </dl>
          <div className="storage-card-actions">
            <button className="secondary-button" type="button" onClick={props.onRefresh}>
              <RefreshCw size={16} />
              Refresh
            </button>
            <span>Database credentials are intentionally hidden.</span>
          </div>
        </article>

        <article className="panel storage-card">
          <div className="storage-card-heading">
            <div className="storage-card-icon"><FileJson size={18} /></div>
            <div>
              <h2>Retention</h2>
              <p>Operational history retention settings</p>
            </div>
          </div>
          <dl className="storage-fields">
            <div><dt>Audit Retention</dt><dd>{props.status ? `${props.status.retention.audit_days} days` : "-"}</dd></div>
            <div><dt>Execution Retention</dt><dd>{props.status ? `${props.status.retention.execution_days} days` : "-"}</dd></div>
            <div><dt>Evidence Retention</dt><dd>{props.status ? `${props.status.retention.evidence_days} days` : "-"}</dd></div>
            <div><dt>Minimum Evidence Runs</dt><dd>{props.status?.retention.evidence_minimum_runs ?? "-"}</dd></div>
          </dl>
          <p className="storage-note">Change storage and retention values with environment variables, then restart the service.</p>
        </article>
      </div>

      <article className="panel storage-backups">
        <div className="storage-backup-heading">
          <div className="storage-card-heading">
            <div className="storage-card-icon"><Download size={18} /></div>
            <div>
              <h2>Database Backups</h2>
              <p>Admin-only PostgreSQL logical exports</p>
            </div>
          </div>
          <div className="toolbar">
            <button className="secondary-button" type="button" onClick={props.onRefresh}>
              <RefreshCw size={16} />
              Refresh
            </button>
            <button className="primary-button" type="button" onClick={props.onCreateBackup} disabled={!backupSupported}>
              <Database size={16} />
              Create Backup
            </button>
          </div>
        </div>
        <p>Create an on-demand PostgreSQL backup for Docker and small-team deployments. Managed PostgreSQL platforms should still use native automated backups.</p>
        {!backupSupported ? <Banner tone="warning" message="PostgreSQL backups are available when the appliance settings database is running on Postgres." /> : null}
        <div className="backup-list">
          {props.status?.backups.length ? props.status.backups.map((backup) => (
            <div className="backup-row" key={backup.name}>
              <div>
                <strong>{backup.name}</strong>
                <span>{formatDateTime(backup.created_at)} - {backup.size_label}</span>
              </div>
              <div className="toolbar">
                <button className="secondary-button" type="button" onClick={() => props.onDownloadBackup(backup.name)}>
                  <Download size={16} />
                  Download
                </button>
                <button className="secondary-button" type="button" onClick={() => props.onBackupDetails(backup.name)}>Details</button>
              </div>
            </div>
          )) : <div className="empty-state">No database backups created yet.</div>}
        </div>
      </article>
    </section>
  );
}

function AboutPage(props: {
  support: SupportStatus | null;
  currentUser: AuthUser | null;
  connections: ManagedConnection[];
  roles: ManagedRole[];
  users: ManagedUser[];
}) {
  const buildInfo = {
    product: "Cluster Assurance Orchestrator for Nutanix Environments",
    uiVersion: APP_VERSION,
    versionTag: APP_VERSION_TAG,
    sourceRef: "not reported",
    commit: "not reported",
    buildDate: "not reported",
    updatePackage: "not reported",
    appliedUpdate: "unknown",
    containerImage: "not reported",
    apiUrl: props.support?.api_url ?? "not reported",
    configSource: props.support?.config_source ?? "not reported",
    evidenceStorage: props.support?.evidence_directory ? "configured locally" : "not reported",
    settingsDatabase: props.support?.admin_database ?? "not reported"
  };

  async function copyBuildInfo() {
    await navigator.clipboard?.writeText(JSON.stringify(buildInfo, null, 2));
  }

  return (
    <section className="panel about-panel">
      <div className="about-heading">
        <div>
          <h2>About Cluster Assurance Orchestrator</h2>
          <p>Cluster Assurance Orchestrator is an independent read-only assurance interface for Nutanix environments.</p>
        </div>
        <button className="secondary-button" type="button" onClick={copyBuildInfo}>
          <ClipboardList size={16} />
          Copy Build Info
        </button>
      </div>
      <div className="about-build-card">
        <div className="about-build-title">
          <span>Installed Build</span>
          <strong>{APP_VERSION_TAG}</strong>
          <p>Use this value to distinguish appliance and UI builds during support handover.</p>
        </div>
        <dl className="about-grid">
          <div><dt>UI Version</dt><dd>{APP_VERSION}</dd></div>
          <div><dt>Version Tag</dt><dd>{APP_VERSION_TAG}</dd></div>
          <div><dt>Source Ref / Patch</dt><dd>{buildInfo.sourceRef}</dd></div>
          <div><dt>Commit</dt><dd>{buildInfo.commit}</dd></div>
          <div><dt>Build Date</dt><dd>{buildInfo.buildDate}</dd></div>
          <div><dt>Update Package</dt><dd>{buildInfo.updatePackage}</dd></div>
          <div><dt>Applied Update</dt><dd>{buildInfo.appliedUpdate}</dd></div>
          <div><dt>Container Image</dt><dd>{buildInfo.containerImage}</dd></div>
        </dl>
      </div>
      <dl className="about-meta">
        <div><dt>Runtime Mode</dt><dd>{props.support ? `${props.support.mode.environment}${props.support.mode.demo_mode ? " / demo" : ""}` : "not reported"}</dd></div>
        <div><dt>API URL</dt><dd>{buildInfo.apiUrl}</dd></div>
        <div><dt>Config Source</dt><dd>{buildInfo.configSource}</dd></div>
        <div><dt>Evidence Storage</dt><dd>{buildInfo.evidenceStorage}</dd></div>
        <div><dt>Settings Database</dt><dd>{buildInfo.settingsDatabase}</dd></div>
        <div><dt>Project</dt><dd>Cluster Assurance Orchestrator</dd></div>
        <div><dt>Supported Scope</dt><dd>Read-only Prism evidence; NCC execution gated</dd></div>
        <div><dt>Signed In As</dt><dd>{props.currentUser?.username ?? "not reported"}</dd></div>
        <div><dt>Role</dt><dd>{props.currentUser?.role_name ?? "not reported"}</dd></div>
        <div><dt>Connections</dt><dd>{props.connections.length} configured / {props.connections.filter((connection) => connection.status === "READY").length} ready</dd></div>
        <div><dt>RBAC</dt><dd>{props.users.length} user(s), {props.roles.length} role(s)</dd></div>
      </dl>
    </section>
  );
}

function NccSettingsPage(props: {
  profiles: NccProfilesResponse | null;
  plan: NccPlan | null;
  catalogue: CatalogueResponse | null;
  selectedCheckIds: string[];
  setSelectedCheckIds: React.Dispatch<React.SetStateAction<string[]>>;
}) {
  const checks = props.catalogue?.checks ?? [];
  const selected = new Set(props.selectedCheckIds);

  function toggleCheck(checkId: string) {
    props.setSelectedCheckIds((current) =>
      current.includes(checkId)
        ? current.filter((selectedCheckId) => selectedCheckId !== checkId)
        : [...current, checkId]
    );
  }

  return (
    <section className="panel">
      <PanelHeading title="NCC Gate" description="Select the health checks that belong in the gated NCC profile. SSH execution remains unavailable." />
      <div className="visual-summary-grid compact-visual">
        <RunVisualCard label="Catalogue Checks" value={checks.length.toString()} status={checks.length ? "HEALTHY" : "UNKNOWN"} detail={`Catalogue v${props.catalogue?.version ?? "-"}`} />
        <RunVisualCard label="Selected" value={`${props.selectedCheckIds.length}`} status={props.selectedCheckIds.length ? "HEALTHY" : "WARNING"} detail="Included in gate profile" />
        <RunVisualCard label="Transport" value={props.profiles?.transport ?? "-"} status={props.profiles?.transport === "ssh" ? "HEALTHY" : "UNKNOWN"} detail={props.profiles?.execution ?? "gated"} />
        <RunVisualCard label="Mandatory" value={checks.filter((check) => check.mandatory).length.toString()} status="WARNING" detail="Cannot be ignored operationally" />
      </div>
      <dl className="details-grid">
        <div><dt>Profiles</dt><dd>{props.profiles?.profiles.length ?? 0}</dd></div>
        <div><dt>Transport</dt><dd>{props.profiles?.transport ?? "not loaded"}</dd></div>
        <div><dt>Execution</dt><dd>{props.profiles?.execution ?? "gated"}</dd></div>
        <div><dt>Selected Checks</dt><dd>{props.selectedCheckIds.length} / {checks.length}</dd></div>
      </dl>
      <div className="toolbar">
        <button className="secondary-button" type="button" onClick={() => props.setSelectedCheckIds(checks.map((check) => check.check_id))}>
          Select all
        </button>
        <button className="secondary-button" type="button" onClick={() => props.setSelectedCheckIds([])}>
          Deselect all
        </button>
      </div>
      <div className="check-list">
        {checks.map((check) => (
          <label className="check-row" key={check.check_id}>
            <input
              type="checkbox"
              checked={selected.has(check.check_id)}
              onChange={() => toggleCheck(check.check_id)}
            />
            <span className="stacked">
              <strong>{check.check_id} - {check.name}</strong>
              <small>{check.source} · {check.default_frequency} · failure maps to {check.failure_outcome}</small>
            </span>
            {check.mandatory ? <span className="status unknown">MANDATORY</span> : null}
          </label>
        ))}
        {!checks.length ? <div className="empty-state">No checks are available from the catalogue.</div> : null}
      </div>
      <DataTable
        columns={["Profile", "Command", "Timeout", "Hash"]}
        rows={(props.profiles?.profiles ?? []).map((profile) => [
          profile.name,
          <span className="mono">{profile.command_display}</span>,
          `${profile.timeout_minutes} min`,
          <span className="mono">{props.plan?.command_hash ? truncate(props.plan.command_hash) : "-"}</span>
        ])}
        emptyText="No NCC profiles are available."
      />
      {props.plan ? <Banner tone="unknown" message={props.plan.reason} /> : null}
    </section>
  );
}

function ConnectionsPage(props: {
  report: IntegrationReport | null;
  alerts: AlertStatus | null;
  connections: ManagedConnection[];
  draft: { name: string; type: ManagedConnection["type"]; url: string; username: string; password: string; tlsMode: string };
  setDraft: React.Dispatch<React.SetStateAction<{ name: string; type: ManagedConnection["type"]; url: string; username: string; password: string; tlsMode: string }>>;
  onAdd: () => void | Promise<void>;
  onUpdate: (connection: ManagedConnection, password: string) => void | Promise<void>;
  onDelete: (connectionId: string) => void | Promise<void>;
  onTest: (connectionId: string) => void | Promise<void>;
}) {
  const [passwordDrafts, setPasswordDrafts] = useState<Record<string, string>>({});
  const readyConnections = props.connections.filter((connection) => connection.status === "READY").length;
  const authFailed = props.connections.filter((connection) => connection.status === "AUTH_FAILED").length;
  const tlsFailed = props.connections.filter((connection) => connection.status === "TLS_FAILED").length;
  const unreachable = props.connections.filter((connection) => connection.status === "UNREACHABLE").length;
  return (
    <>
      <section className="panel">
        <PanelHeading title="Connections" description="Add Prism Central or Prism Element endpoints with redacted credential storage." />
        <div className="visual-summary-grid compact-visual">
          <RunVisualCard label="Configured" value={props.connections.length.toString()} status={props.connections.length ? "HEALTHY" : "UNKNOWN"} detail="Prism endpoints" />
          <RunVisualCard label="Ready" value={readyConnections.toString()} status={readyConnections ? "HEALTHY" : "UNKNOWN"} detail="Read-only probe passed" />
          <RunVisualCard label="Credential / TLS" value={`${authFailed + tlsFailed}`} status={authFailed + tlsFailed ? "WARNING" : "HEALTHY"} detail={`${authFailed} auth, ${tlsFailed} TLS`} />
          <RunVisualCard label="Unreachable" value={unreachable.toString()} status={unreachable ? "WARNING" : "HEALTHY"} detail="Network or endpoint issue" />
        </div>
        <div className="form-grid connection-form">
          <label>
            <span>Name</span>
            <input value={props.draft.name} onChange={(event) => props.setDraft((draft) => ({ ...draft, name: event.target.value }))} placeholder="Production Prism Central" />
          </label>
          <label>
            <span>Type</span>
            <select value={props.draft.type} onChange={(event) => props.setDraft((draft) => ({ ...draft, type: event.target.value as ManagedConnection["type"] }))}>
              <option>Prism Central</option>
              <option>Prism Element</option>
            </select>
          </label>
          <label>
            <span>URL</span>
            <input value={props.draft.url} onChange={(event) => props.setDraft((draft) => ({ ...draft, url: event.target.value }))} placeholder="https://cluster.example:9440/" />
          </label>
          <label>
            <span>Username</span>
            <input value={props.draft.username} onChange={(event) => props.setDraft((draft) => ({ ...draft, username: event.target.value }))} placeholder="admin" />
          </label>
          <label>
            <span>Password</span>
            <input value={props.draft.password} onChange={(event) => props.setDraft((draft) => ({ ...draft, password: event.target.value }))} placeholder="Store credential" type="password" />
          </label>
          <label>
            <span>TLS Mode</span>
            <select value={props.draft.tlsMode} onChange={(event) => props.setDraft((draft) => ({ ...draft, tlsMode: event.target.value }))}>
              <option value="strict">Strict</option>
              <option value="insecure_skip_verify">Insecure skip verify</option>
            </select>
          </label>
          <button className="primary-button" type="button" onClick={props.onAdd}>
            <Plus size={16} />
            Add connection
          </button>
        </div>
        <DataTable
          columns={["Name", "Type", "URL", "Credential", "State", "Rotate / Actions"]}
          rows={props.connections.map((connection) => [
            connection.name,
            connection.type,
            <span className="stacked"><strong>{connection.url}</strong><small>{connection.username || "No username"} · {connection.tlsMode} · checked {connection.lastCheckedAt ? formatDate(connection.lastCheckedAt) : "never"}</small></span>,
            connection.secretSet ? "Stored redacted" : "Missing",
            <span className={`status ${connection.status === "READY" ? "healthy" : "unknown"}`}>{connection.status}</span>,
            <span className="row-actions">
              <input
                className="inline-secret"
                type="password"
                placeholder="New password"
                value={passwordDrafts[connection.id] ?? ""}
                onChange={(event) => setPasswordDrafts((current) => ({ ...current, [connection.id]: event.target.value }))}
                aria-label={`${connection.name} new password`}
              />
              <button className="table-action" type="button" onClick={async () => {
                await props.onUpdate(connection, passwordDrafts[connection.id] ?? "");
                setPasswordDrafts((current) => ({ ...current, [connection.id]: "" }));
              }}>
                <KeyRound size={14} />
                Rotate
              </button>
              <button className="table-action" type="button" onClick={() => props.onTest(connection.id)}>
                <RefreshCw size={14} />
                Test
              </button>
              <button className="table-action danger" type="button" onClick={() => props.onDelete(connection.id)} aria-label={`Delete ${connection.name}`}>
                <Trash2 size={14} />
                Delete
              </button>
            </span>
          ])}
          emptyText="No Prism connections are configured."
        />
      </section>
      <section className="panel">
        <PanelHeading title="External Adapters" description="Notification and ITSM adapters remain disabled until endpoint controls and delivery audit are complete." />
        <dl className="details-grid compact">
          <div><dt>Alerting</dt><dd>{props.alerts?.enabled ? "Enabled" : "Disabled"}</dd></div>
          <div><dt>Trusted evidence</dt><dd>{props.alerts?.trustworthy_evidence ? "Yes" : "No"}</dd></div>
          <div><dt>Email</dt><dd>{props.alerts?.email.state ?? "-"}</dd></div>
          <div><dt>Webhook</dt><dd>{props.alerts?.webhook.state ?? "-"}</dd></div>
        </dl>
        {props.alerts?.reason ? <Banner tone="warning" message={props.alerts.reason} /> : null}
        <DataTable
          columns={["Adapter", "State", "Events", "Summary"]}
          rows={(props.report?.adapters ?? []).map((adapter) => [
            <span className="stacked"><strong>{adapter.name}</strong><small>{adapter.category}</small></span>,
            <span className={`status ${integrationTone(adapter.state)}`}>{adapter.state}</span>,
            adapter.supported_events.join(", "),
            adapter.summary
          ])}
          emptyText="No integration adapters are defined."
        />
      </section>
    </>
  );
}

function ReadinessPage(props: { report: SecurityReadinessReport | null }) {
  const gates = props.report?.gates ?? [];
  const passCount = gates.filter((gate) => gate.status === "PASS").length;
  const blockedCount = gates.filter((gate) => gate.status === "BLOCKED").length;
  const warningCount = gates.filter((gate) => gate.status === "WARNING").length;
  return (
    <section className="panel">
      <PanelHeading title="Readiness Gates" description="Production approval remains blocked until these controls are closed and evidenced." />
      <div className="visual-summary-grid compact-visual">
        <RunVisualCard label="Passed" value={passCount.toString()} status="HEALTHY" detail={`${gates.length} total gate(s)`} />
        <RunVisualCard label="Blocked" value={blockedCount.toString()} status={blockedCount ? "CRITICAL" : "HEALTHY"} detail="Blocks production claims" />
        <RunVisualCard label="Warnings" value={warningCount.toString()} status={warningCount ? "WARNING" : "HEALTHY"} detail="Needs evidence or closure" />
        <RunVisualCard label="Maturity" value={props.report?.maturity ?? "-"} status={blockedCount || warningCount ? "WARNING" : "HEALTHY"} detail="Readiness posture" />
      </div>
      <DataTable
        columns={["Gate", "Status", "Summary", "Evidence"]}
        rows={(props.report?.gates ?? []).map((gate) => [
          gate.name,
          <span className={`status ${gateTone(gate.status).toLowerCase()}`}>{gate.status}</span>,
          gate.summary,
          gate.evidence.join(", ")
        ])}
        emptyText="No readiness gates are available."
      />
    </section>
  );
}

function RbacPage(props: {
  roles: ManagedRole[];
  setRoles: React.Dispatch<React.SetStateAction<ManagedRole[]>>;
  roleDraft: { name: string; permissions: string };
  setRoleDraft: React.Dispatch<React.SetStateAction<{ name: string; permissions: string }>>;
  users: ManagedUser[];
  setUsers: React.Dispatch<React.SetStateAction<ManagedUser[]>>;
  userDraft: { username: string; name: string; email: string; roleId: string; status: ManagedUser["status"]; password: string };
  setUserDraft: React.Dispatch<React.SetStateAction<{ username: string; name: string; email: string; roleId: string; status: ManagedUser["status"]; password: string }>>;
  passwordDrafts: Record<string, string>;
  setPasswordDrafts: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  onAddRole: () => void;
  onAddUser: () => void;
  onSetPassword: (userId: string) => void;
  onUpdateUser: (user: ManagedUser) => void;
  onDeleteUser: (userId: string) => void;
  onUpdateRole: (role: ManagedRole) => void;
  onDeleteRole: (roleId: string) => void;
}) {
  const adminRole = props.roles.find((role) => permissionList(role.permissions).includes("all_permissions"));
  const disabledUsers = props.users.filter((user) => user.status === "Disabled").length;
  const missingPasswords = props.users.filter((user) => !user.passwordSet).length;
  return (
    <>
      <section className="panel">
        <PanelHeading title="User Accounts" description="Create accounts, set passwords and manage local role assignments for the future auth layer." />
        <div className="visual-summary-grid compact-visual">
          <RunVisualCard label="Users" value={props.users.length.toString()} status={props.users.length ? "HEALTHY" : "UNKNOWN"} detail={`${disabledUsers} disabled`} />
          <RunVisualCard label="Passwords" value={missingPasswords ? `${missingPasswords} missing` : "Set"} status={missingPasswords ? "WARNING" : "HEALTHY"} detail="Local account secrets" />
          <RunVisualCard label="Roles" value={props.roles.length.toString()} status={props.roles.length ? "HEALTHY" : "UNKNOWN"} detail={adminRole ? "Admin role present" : "Admin role missing"} />
          <RunVisualCard label="Access Model" value="Local RBAC" status="HEALTHY" detail="Server-side enforcement active" />
        </div>
        <div className="form-grid user-form">
          <label>
            <span>Username</span>
            <input value={props.userDraft.username} onChange={(event) => props.setUserDraft((draft) => ({ ...draft, username: event.target.value }))} placeholder="jane.operator" />
          </label>
          <label>
            <span>Name</span>
            <input value={props.userDraft.name} onChange={(event) => props.setUserDraft((draft) => ({ ...draft, name: event.target.value }))} placeholder="Jane Operator" />
          </label>
          <label>
            <span>Email</span>
            <input value={props.userDraft.email} onChange={(event) => props.setUserDraft((draft) => ({ ...draft, email: event.target.value }))} placeholder="jane@example.com" />
          </label>
          <label>
            <span>Role</span>
            <select value={props.userDraft.roleId} onChange={(event) => props.setUserDraft((draft) => ({ ...draft, roleId: event.target.value }))}>
              {props.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
            </select>
          </label>
          <label>
            <span>Status</span>
            <select value={props.userDraft.status} onChange={(event) => props.setUserDraft((draft) => ({ ...draft, status: event.target.value as ManagedUser["status"] }))}>
              <option>Active</option>
              <option>Disabled</option>
            </select>
          </label>
          <label>
            <span>Password</span>
            <input
              value={props.userDraft.password}
              onChange={(event) => props.setUserDraft((draft) => ({ ...draft, password: event.target.value }))}
              placeholder="Set initial password"
              type="password"
            />
          </label>
          <button className="primary-button" type="button" onClick={props.onAddUser}>
            <Plus size={16} />
            Create user
          </button>
        </div>
        <div className="editable-list">
          {props.users.map((user) => (
            <div className="editable-row user-row" key={user.id}>
              <input value={user.username} onChange={(event) => props.setUsers((current) => current.map((item) => item.id === user.id ? { ...item, username: event.target.value } : item))} aria-label={`${user.name} username`} />
              <input value={user.name} onChange={(event) => props.setUsers((current) => current.map((item) => item.id === user.id ? { ...item, name: event.target.value } : item))} aria-label={`${user.name} name`} />
              <input value={user.email} onChange={(event) => props.setUsers((current) => current.map((item) => item.id === user.id ? { ...item, email: event.target.value } : item))} aria-label={`${user.name} email`} />
              <select value={user.roleId} onChange={(event) => props.setUsers((current) => current.map((item) => item.id === user.id ? { ...item, roleId: event.target.value } : item))} aria-label={`${user.name} role`}>
                {props.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}
              </select>
              <select value={user.status} onChange={(event) => props.setUsers((current) => current.map((item) => item.id === user.id ? { ...item, status: event.target.value as ManagedUser["status"] } : item))} aria-label={`${user.name} status`}>
                <option>Active</option>
                <option>Disabled</option>
              </select>
              <div className="password-reset">
                <input
                  aria-label={`${user.name} new password`}
                  placeholder={user.passwordSet ? "Reset password" : "Set password"}
                  type="password"
                  value={props.passwordDrafts[user.id] ?? ""}
                  onChange={(event) => props.setPasswordDrafts((current) => ({ ...current, [user.id]: event.target.value }))}
                />
                <button className="table-action" type="button" onClick={() => props.onSetPassword(user.id)}>
                  <KeyRound size={14} />
                  {user.passwordSet ? "Reset" : "Set"}
                </button>
                <span className="password-state">{user.passwordSet ? `Updated ${user.passwordUpdatedAt ? formatDate(user.passwordUpdatedAt) : "recently"}` : "No password"}</span>
              </div>
              <span className="row-actions">
                <button className="table-action" type="button" onClick={() => props.onUpdateUser(user)}>
                  Save
                </button>
                <button className="table-action danger" type="button" onClick={() => props.onDeleteUser(user.id)}>
                  <Trash2 size={14} />
                  Delete
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Roles" description="Modify role names and permissions before server-side RBAC enforcement is added." />
        <div className="form-grid">
          <label>
            <span>Role name</span>
            <input value={props.roleDraft.name} onChange={(event) => props.setRoleDraft((draft) => ({ ...draft, name: event.target.value }))} placeholder="Auditor" />
          </label>
          <label className="wide-field">
            <span>Permissions</span>
            <input value={props.roleDraft.permissions} onChange={(event) => props.setRoleDraft((draft) => ({ ...draft, permissions: event.target.value }))} placeholder="view_dashboard, view_evidence" />
          </label>
          <button className="primary-button" type="button" onClick={props.onAddRole}>
            <Plus size={16} />
            Create role
          </button>
        </div>
        <div className="editable-list">
          {props.roles.map((role) => (
            <div className="editable-row role-row" key={role.id}>
              <input value={role.name} onChange={(event) => props.setRoles((current) => current.map((item) => item.id === role.id ? { ...item, name: event.target.value } : item))} aria-label={`${role.name} role name`} />
              <input value={role.permissions} onChange={(event) => props.setRoles((current) => current.map((item) => item.id === role.id ? { ...item, permissions: event.target.value } : item))} aria-label={`${role.name} permissions`} />
              <span className="row-actions">
                <button className="table-action" type="button" onClick={() => props.onUpdateRole(role)}>
                  Save
                </button>
                <button
                  className="table-action danger"
                  type="button"
                  disabled={props.users.some((user) => user.roleId === role.id)}
                  onClick={() => props.onDeleteRole(role.id)}
                  title={props.users.some((user) => user.roleId === role.id) ? "Role is assigned to a user" : "Delete role"}
                >
                  <Trash2 size={14} />
                  Delete
                </button>
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <PanelHeading title="Permission Preview" description="Quickly inspect what each local role can do before changing account assignments." />
        <DataTable
          columns={["Role", "Users", "Can run checks", "Can manage schedules", "Can manage secrets", "Can view evidence"]}
          rows={props.roles.map((role) => {
            const permissions = new Set(permissionList(role.permissions));
            const admin = permissions.has("all_permissions");
            return [
              role.name,
              props.users.filter((user) => user.roleId === role.id).length.toString(),
              yesNo(admin || permissions.has("run_read_only_inventory")),
              yesNo(admin || permissions.has("manage_schedules")),
              yesNo(admin),
              yesNo(admin || permissions.has("view_evidence"))
            ];
          })}
          emptyText="No roles are available."
        />
      </section>
    </>
  );
}

function AuditEventsPage(props: { events: AuditEvent[] }) {
  const [query, setQuery] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const actions = Array.from(new Set(props.events.map((event) => event.action))).sort();
  const filteredEvents = props.events.filter((event) => {
    const matchesAction = actionFilter === "all" || event.action === actionFilter;
    const haystack = `${event.actor_username ?? "system"} ${event.action} ${event.target_type} ${event.target_id} ${JSON.stringify(event.details)}`.toLowerCase();
    return matchesAction && haystack.includes(query.toLowerCase());
  });
  const authEvents = props.events.filter((event) => event.action.toLowerCase().includes("login") || event.action.toLowerCase().includes("sign")).length;
  const secretEvents = props.events.filter((event) => event.action.toLowerCase().includes("credential") || event.action.toLowerCase().includes("password") || event.action.toLowerCase().includes("connection")).length;
  return (
    <section className="panel">
      <PanelHeading title="Audit Log" description="Append-only administrative events for sign-in, RBAC, connection and credential changes." />
      <div className="visual-summary-grid compact-visual">
        <RunVisualCard label="Events" value={props.events.length.toString()} status={props.events.length ? "HEALTHY" : "UNKNOWN"} detail="Persisted audit records" />
        <RunVisualCard label="Auth Events" value={authEvents.toString()} status={authEvents ? "HEALTHY" : "UNKNOWN"} detail="Sign-in activity" />
        <RunVisualCard label="Secret Changes" value={secretEvents.toString()} status={secretEvents ? "WARNING" : "HEALTHY"} detail="Review credential movement" />
        <RunVisualCard label="Visible" value={filteredEvents.length.toString()} status="HEALTHY" detail="After filters" />
      </div>
      <div className="toolbar filter-toolbar">
        <label>
          <span>Search</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="actor, action, target" />
        </label>
        <label>
          <span>Action</span>
          <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
            <option value="all">All actions</option>
            {actions.map((action) => <option key={action} value={action}>{action}</option>)}
          </select>
        </label>
      </div>
      <DataTable
        columns={["Time", "Actor", "Action", "Target", "Details"]}
        rows={filteredEvents.map((event) => [
          formatDate(event.occurred_at),
          event.actor_username ?? "system",
          event.action,
          `${event.target_type}:${event.target_id}`,
          Object.keys(event.details).length ? JSON.stringify(event.details) : "-"
        ])}
        emptyText="No audit events are available."
      />
    </section>
  );
}

function AuditPanel(props: {
  run: InventoryRun | null;
  schedule: SchedulePreview | null;
  nccPlan: NccPlan | null;
  readiness: SecurityReadinessReport | null;
}) {
  const events = [
    ...(props.run?.warnings ?? ["No inventory evidence loaded."]),
    ...(props.schedule?.active_locks.map(
      (lock) => `Cluster ${lock.cluster_id} has preview lock ${lock.owner_run_id} until ${formatDate(lock.expires_at)}.`
    ) ?? []),
    ...(props.nccPlan?.warnings ?? []),
    ...(props.readiness?.open_risks ?? [])
  ];
  return (
    <section className="panel">
      <PanelHeading title="Audit Log" description="Derived safety events for this phase. A persistent append-only audit store comes later." />
      <ul className="event-list">
        {events.map((event) => <li key={event}>{event}</li>)}
      </ul>
    </section>
  );
}

function OpsStripItem(props: { label: string; value: string; detail: string; status: HealthStatus }) {
  return (
    <article className={`ops-strip-item ${props.status.toLowerCase()}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      <small>{props.detail}</small>
    </article>
  );
}

function TriageStep(props: {
  number: string;
  title: string;
  status: HealthStatus;
  detail: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <article className={`triage-step ${props.status.toLowerCase()}`}>
      <div className="triage-step-top">
        <span className="triage-number">{props.number}</span>
        <StatusBadge status={props.status} />
      </div>
      <h3>{props.title}</h3>
      <p>{props.detail}</p>
      <button className="table-action" type="button" onClick={props.onAction}>{props.action}</button>
    </article>
  );
}

function OperatorCard(props: {
  icon: React.ReactNode;
  title: string;
  status: HealthStatus;
  summary: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <article className={`operator-card ${props.status.toLowerCase()}`}>
      <div className="operator-card-icon">{props.icon}</div>
      <div className="operator-card-body">
        <div className="operator-card-title">
          <h3>{props.title}</h3>
          <StatusBadge status={props.status} />
        </div>
        <p>{props.summary}</p>
      </div>
      <button className="table-action" type="button" onClick={props.onAction}>{props.action}</button>
    </article>
  );
}

function DomainHealthGrid(props: {
  title: string;
  description: string;
  domains: OperationalDomain[];
  onNavigate: (page: PageId) => void;
}) {
  return (
    <section className="panel">
      <PanelHeading title={props.title} description={props.description} />
      <div className="domain-grid">
        {props.domains.map((domain) => (
          <article className={`domain-card ${domain.status.toLowerCase()}`} key={domain.id}>
            <div className="domain-card-top">
              <div className="domain-icon">{domainIcon(domain.id)}</div>
              <StatusBadge status={domain.status} />
            </div>
            <h3>{domain.label}</h3>
            <strong>{domain.value}</strong>
            <p>{domain.detail}</p>
            <div className="domain-meter" aria-label={`${domain.label} evidence coverage ${domain.coverage}%`}>
              <span style={{ width: `${domain.coverage}%` }} />
            </div>
            <small>{domain.evidence}</small>
            <button className="table-action" type="button" onClick={() => props.onNavigate(domain.actionPage)}>{domain.action}</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function RunVisualCard(props: { label: string; value: string; status: HealthStatus; detail: string }) {
  return (
    <article className={`run-visual-card ${props.status.toLowerCase()}`}>
      <div>
        <span>{props.label}</span>
        <strong>{props.value}</strong>
      </div>
      <StatusBadge status={props.status} />
      <p>{props.detail}</p>
    </article>
  );
}

function EvidenceStep(props: { icon: React.ReactNode; label: string; status: HealthStatus; detail: string }) {
  return (
    <article className={`evidence-step ${props.status.toLowerCase()}`}>
      <div className="evidence-step-icon">{props.icon}</div>
      <div>
        <strong>{props.label}</strong>
        <p>{props.detail}</p>
      </div>
      <StatusBadge status={props.status} />
    </article>
  );
}

function CollectorTable(props: { collectors: Collector[] }) {
  return (
    <DataTable
      columns={["Collector", "Status", "HTTP", "Summary"]}
      rows={props.collectors.map((collector) => [
        `${collector.endpoint_alias} - ${collector.method} ${collector.path}`,
        <StatusBadge status={collector.status} />,
        collector.status_code?.toString() ?? "-",
        collector.summary
      ])}
      emptyText="No collector evidence found."
    />
  );
}

function Metric(props: { icon: React.ReactNode; label: string; value: string; tone?: string }) {
  return (
    <article className={`metric ${props.tone ?? ""}`}>
      <div className="metric-icon">{props.icon}</div>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </article>
  );
}

function PanelHeading(props: { title: string; description: string }) {
  return (
    <div className="panel-heading">
      <h2>{props.title}</h2>
      <p>{props.description}</p>
    </div>
  );
}

function Banner(props: { message: string; tone?: string }) {
  return <div className={`banner ${props.tone ?? ""}`}>{props.message}</div>;
}

function StatusBadge(props: { status: HealthStatus }) {
  return <span className={`status ${props.status.toLowerCase()}`}>{props.status}</span>;
}

function DataTable(props: { columns: string[]; rows: React.ReactNode[][]; emptyText: string }) {
  const template = `repeat(${props.columns.length}, minmax(0, 1fr))`;
  return (
    <div className="data-table" role="table">
      <div className="data-row header" role="row" style={{ gridTemplateColumns: template }}>
        {props.columns.map((column) => <span key={column}>{column}</span>)}
      </div>
      {props.rows.length ? props.rows.map((row, rowIndex) => (
        <div className="data-row" role="row" style={{ gridTemplateColumns: template }} key={rowIndex}>
          {row.map((cell, cellIndex) => <span key={cellIndex}>{cell}</span>)}
        </div>
      )) : <div className="empty-state">{props.emptyText}</div>}
    </div>
  );
}

async function fetchJson<T>(path: string, init: RequestInit = {}, token = ""): Promise<T> {
  if (STATIC_DEMO) {
    return demoJsonResponse<T>(path, init);
  }
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `${path} returned HTTP ${response.status}`;
    try {
      const payload = await response.json() as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep the HTTP fallback when the server did not return JSON.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

async function fetchBlob(path: string, token = ""): Promise<Blob> {
  if (STATIC_DEMO) {
    return new Blob([`Static demo export placeholder for ${path}`], { type: "text/plain" });
  }
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    let detail = `${path} returned HTTP ${response.status}`;
    try {
      const payload = await response.json() as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep the HTTP fallback when the server did not return JSON.
    }
    throw new Error(detail);
  }
  return response.blob();
}

async function demoJsonResponse<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  if (path === "/api/v1/auth/login") {
    return { token: "static-demo-token", user: demoUser } as T;
  }
  if (path === "/api/v1/auth/logout") {
    return { status: "ok" } as T;
  }
  if (path === "/api/v1/lab/inventory-runs/latest") {
    return demoRun as T;
  }
  if (path === "/api/v1/schedules/preview/default") {
    return demoSchedule as T;
  }
  if (path === "/api/v1/ncc/profiles") {
    return demoNccProfiles as T;
  }
  if (path === "/api/v1/ncc/plan") {
    return demoNccPlan as T;
  }
  if (path === "/api/v1/evidence/manifest/latest") {
    return demoManifest as T;
  }
  if (path === "/api/v1/integrations/status") {
    return demoIntegrations as T;
  }
  if (path === "/api/v1/security/readiness") {
    return demoReadiness as T;
  }
  if (path === "/api/v1/catalogue") {
    return demoCatalogue as T;
  }
  if (path === "/api/v1/support/status") {
    return demoSupportStatus as T;
  }
  if (path === "/api/v1/health-runs/history") {
    return demoHealthRunHistory as T;
  }
  if (path === "/api/v1/evidence/retention" || path === "/api/v1/evidence/retention/prune") {
    return demoRetention as T;
  }
  if (path === "/api/v1/alerts/status") {
    return demoAlerts as T;
  }
  if (path === "/api/v1/rbac/roles") {
    return demoRoles.map((role) => ({ id: role.id, name: role.name, permissions: permissionList(role.permissions) })) as T;
  }
  if (path === "/api/v1/rbac/users") {
    return demoUsers.map((user) => ({
      id: user.id,
      username: user.username,
      name: user.name,
      email: user.email,
      role_id: user.roleId,
      role_name: user.roleName,
      status: user.status,
      password_set: user.passwordSet,
      password_updated_at: user.passwordUpdatedAt
    })) as T;
  }
  if (path === "/api/v1/connections") {
    return demoConnections.map((connection) => ({
      id: connection.id,
      name: connection.name,
      type: connection.type,
      url: connection.url,
      username: connection.username,
      secret_set: connection.secretSet,
      tls_mode: connection.tlsMode,
      status: connection.status,
      last_checked_at: connection.lastCheckedAt
    })) as T;
  }
  if (path === "/api/v1/audit/events") {
    return demoAuditEvents as T;
  }
  if (path === "/api/v1/storage/status") {
    return demoStorageStatus as T;
  }
  if (path === "/api/v1/storage/backups" && method === "POST") {
    return demoStorageStatus.backups[0] as T;
  }
  if (path.startsWith("/api/v1/storage/backups/")) {
    return { ...demoStorageStatus.backups[0], storage: "static demo data" } as T;
  }
  if (path === "/api/v1/health-runs/manual") {
    return { run_id: demoRun.run_id, status: demoRun.status, evidence_path: "demo://evidence/latest" } as T;
  }
  if (path === "/api/v1/schedules") {
    return (method === "GET" ? demoSchedules : demoSchedules[0]) as T;
  }
  if (path === "/api/v1/schedules/runs/history") {
    return demoScheduleHistory as T;
  }
  if (path === "/api/v1/schedules/run-due") {
    return { due_schedules: 1 } as T;
  }
  if (/^\/api\/v1\/schedules\/[^/]+\/run-now$/.test(path)) {
    return demoScheduleHistory[0] as T;
  }
  if (path.startsWith("/api/v1/schedules/")) {
    return (method === "DELETE" ? { status: "demo" } : demoSchedules[0]) as T;
  }
  return { status: "static-demo" } as T;
}

function unwrap<T>(
  result: PromiseSettledResult<T>,
  setter: React.Dispatch<React.SetStateAction<T | null>>
): T | null {
  if (result.status === "fulfilled") {
    setter(result.value);
    return result.value;
  }
  setter(null);
  return null;
}

function isAuthError(error: unknown) {
  if (!(error instanceof Error)) {
    return false;
  }
  return /invalid or expired session|bearer token required|http 401/i.test(error.message);
}

function labelize(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString();
}

function formatBytes(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function scheduleStatusTone(value: string) {
  if (value === "ready") {
    return "healthy";
  }
  if (value === "partial") {
    return "warning";
  }
  return "unknown";
}

function scheduleRunTone(value: string) {
  if (value === "HEALTHY" || value === "PASS") {
    return "healthy";
  }
  if (value === "WARNING" || value.startsWith("SKIPPED")) {
    return "warning";
  }
  if (value === "CRITICAL" || value === "FAILED") {
    return "critical";
  }
  return "unknown";
}

function scheduleRunStatus(value?: string): HealthStatus {
  if (!value) {
    return "UNKNOWN";
  }
  if (value === "HEALTHY" || value === "PASS" || value === "COMPLETED") {
    return "HEALTHY";
  }
  if (value === "WARNING" || value.startsWith("SKIPPED")) {
    return "WARNING";
  }
  if (value === "CRITICAL" || value === "FAILED") {
    return "CRITICAL";
  }
  return "UNKNOWN";
}

function integrationTone(value: string) {
  if (value === "READY") {
    return "healthy";
  }
  if (value === "ERROR") {
    return "critical";
  }
  return "warning";
}

function gateTone(value: string): HealthStatus {
  if (value === "PASS") {
    return "HEALTHY";
  }
  if (value === "BLOCKED") {
    return "CRITICAL";
  }
  if (value === "WARNING") {
    return "WARNING";
  }
  return "UNKNOWN";
}

function yesNo(value: boolean) {
  return value ? "Yes" : "No";
}

function evidenceConfidence(support: SupportStatus | null): { status: HealthStatus; label: string; detail: string } {
  if (!support?.latest_run.available) {
    return { status: "UNKNOWN", label: "No evidence", detail: "Run a health check to create local evidence." };
  }
  if (support.mode.demo_mode) {
    return { status: "UNKNOWN", label: "Synthetic", detail: "Demo evidence only; Prism was not contacted." };
  }
  if (support.collector_failures.length) {
    return { status: "WARNING", label: "Partial", detail: `${support.collector_failures.length} collector(s) failed.` };
  }
  if (support.latest_run.age_seconds != null && support.latest_run.age_seconds > 24 * 60 * 60) {
    return { status: "WARNING", label: "Stale", detail: "Latest evidence is older than 24 hours." };
  }
  if (support.mode.tls_mode === "insecure_skip_verify") {
    return { status: "WARNING", label: "Live Prism / lab TLS", detail: "Read-only Prism evidence with TLS verification disabled." };
  }
  return { status: "HEALTHY", label: "Live Prism", detail: "Read-only Prism evidence with strict TLS." };
}

function operationalDomains(run: InventoryRun | null, support: SupportStatus | null): OperationalDomain[] {
  const collectorCount = run?.collectors.length ?? 0;
  const healthyCollectors = run?.collectors.filter((collector) => collector.status === "HEALTHY").length ?? 0;
  const inventoryCollectors = collectorsForDomain(run, "inventory");
  const inventoryCoverage = inventoryCollectors.length ? collectorCoverage(inventoryCollectors) : 0;
  const evidenceAge = support?.latest_run.age_seconds != null ? formatAge(support.latest_run.age_seconds) : "age unknown";
  return [
    {
      id: "inventory",
      label: "Inventory Collection",
      status: domainStatus(inventoryCollectors, run?.status ?? "UNKNOWN"),
      value: `${run?.clusters.length ?? 0} cluster(s)`,
      detail: inventoryCollectors.length ? `${inventoryCollectors.filter((collector) => collector.status === "HEALTHY").length}/${inventoryCollectors.length} collector(s) healthy; latest evidence ${evidenceAge}.` : "Run a health check to collect Prism inventory.",
      coverage: inventoryCoverage || (collectorCount ? Math.round((healthyCollectors / collectorCount) * 100) : 0),
      evidence: "Collected from configured Prism read-only probes.",
      action: "Review runs",
      actionPage: "runs"
    },
    domainCollectorCard(run, "storage", "Storage Health", "Track storage pools, containers, disk capacity, resiliency and critical storage alerts.", "Review findings", "findings"),
    domainCollectorCard(run, "hardware", "Hardware Health", "Track nodes, disks, CVMs, power, fans and host hardware fault posture where Prism exposes it.", "Review estate", "estate"),
    domainCollectorCard(run, "network", "Network Health", "Track host NIC/link state, CVM connectivity, cluster services and Prism-reported network alerts.", "Check connections", "settings"),
    domainCollectorCard(run, "capacity", "Resource Capacity", "Track CPU, memory and storage headroom with trend history before alerting or forecasting.", "Review schedules", "schedules")
  ];
}

function domainCollectorCard(
  run: InventoryRun | null,
  id: OperationalDomain["id"],
  label: string,
  fallbackDetail: string,
  action: string,
  actionPage: PageId
): OperationalDomain {
  const collectors = collectorsForDomain(run, id);
  if (!collectors.length) {
    return {
      id,
      label,
      status: "UNKNOWN",
      value: "Collector needed",
      detail: fallbackDetail,
      coverage: 0,
      evidence: `No trusted ${id} evidence yet.`,
      action,
      actionPage
    };
  }
  const healthy = collectors.filter((collector) => collector.status === "HEALTHY").length;
  const itemCount = collectors.reduce((total, collector) => total + (collector.item_count ?? 0), 0);
  const issue = collectors.find((collector) => collector.status !== "HEALTHY");
  return {
    id,
    label,
    status: domainStatus(collectors, "UNKNOWN"),
    value: `${healthy}/${collectors.length} ready`,
    detail: issue?.summary ?? `${itemCount} ${id} record(s) captured from configured Prism endpoint(s).`,
    coverage: collectorCoverage(collectors),
    evidence: `Latest run includes ${collectors.length} ${id} collector artifact(s).`,
    action,
    actionPage
  };
}

function collectorsForDomain(run: InventoryRun | null, domain: string) {
  return (run?.collectors ?? []).filter((collector) => (collector.domain ?? "inventory") === domain);
}

function collectorCoverage(collectors: Collector[]) {
  return collectors.length ? Math.round((collectors.filter((collector) => collector.status === "HEALTHY").length / collectors.length) * 100) : 0;
}

function domainStatus(collectors: Collector[], fallback: HealthStatus): HealthStatus {
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

function domainIcon(domainId: OperationalDomain["id"]) {
  if (domainId === "storage") {
    return <Database size={22} />;
  }
  if (domainId === "hardware") {
    return <TerminalSquare size={22} />;
  }
  if (domainId === "network") {
    return <Network size={22} />;
  }
  if (domainId === "capacity") {
    return <Gauge size={22} />;
  }
  return <Activity size={22} />;
}

function runChangeSummary(history: HealthRunHistoryItem[]) {
  if (history.length < 2) {
    return "No previous run comparison";
  }
  const [latest, previous] = history;
  const clusterDelta = latest.cluster_count - previous.cluster_count;
  const failureDelta = latest.collector_failure_count - previous.collector_failure_count;
  const changes = [
    clusterDelta === 0 ? "clusters unchanged" : `${clusterDelta > 0 ? "+" : ""}${clusterDelta} cluster(s)`,
    failureDelta === 0 ? "collector issues unchanged" : `${failureDelta > 0 ? "+" : ""}${failureDelta} collector issue(s)`
  ];
  if (latest.status !== previous.status) {
    changes.unshift(`status ${previous.status} to ${latest.status}`);
  }
  return changes.join(", ");
}

function runChangeStatus(latest: HealthRunHistoryItem | null, previous: HealthRunHistoryItem | null): HealthStatus {
  if (!latest || !previous) {
    return "UNKNOWN";
  }
  if (latest.status !== previous.status || latest.collector_failure_count !== previous.collector_failure_count) {
    return latest.collector_failure_count > previous.collector_failure_count ? "WARNING" : "HEALTHY";
  }
  return "HEALTHY";
}

function dashboardReason(primaryIssue: Collector | null, support: SupportStatus | null) {
  if (primaryIssue) {
    if (support?.mode.demo_mode) {
      return `Latest saved evidence shows ${collectorTitle(primaryIssue).toLowerCase()}. Run a new health check after testing the saved connection.`;
    }
    if (primaryIssue.status_code === 401 || primaryIssue.status_code === 403) {
      return `Latest evidence shows ${collectorTitle(primaryIssue).toLowerCase()}. Test the saved connection and rerun health collection.`;
    }
    return primaryIssue.summary;
  }
  if (support?.warnings[0]) {
    return support.warnings[0];
  }
  return "No collector issues are recorded for the latest evidence.";
}

function collectorTitle(collector: Collector) {
  const source = labelize(collector.source);
  if (collector.status_code === 401 || collector.status_code === 403) {
    return `${source} collector authentication failed`;
  }
  if (collector.status === "UNKNOWN") {
    return `${source} collector is unknown`;
  }
  return `${source} collector attention`;
}

function permissionList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function splitTargets(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function buildScheduleRequest(definition: ScheduleRequestInput) {
  const targets = definition.target_cluster_ids.length ? definition.target_cluster_ids : ["no-lab-inventory"];
  return {
    schedule_id: definition.schedule_id,
    name: definition.name,
    profile: {
      profile_id: definition.profile?.profile_id ?? "daily-standard",
      name: definition.profile?.name ?? "Daily Standard",
      version: definition.profile?.version ?? 1,
      definition_hash: definition.profile?.definition_hash ?? "ui-defined",
      checks: definition.profile?.checks?.length ? definition.profile.checks : ["HC-001", "HC-002", "HC-003", "HC-016"],
      timeout_minutes: definition.profile?.timeout_minutes ?? 30
    },
    target_cluster_ids: targets,
    timezone: definition.timezone,
    recurrence: definition.recurrence,
    start_time: definition.start_time,
    weekly_day: definition.weekly_day,
    enabled: definition.enabled,
    misfire_policy: definition.misfire_policy || "run_within_grace",
    misfire_grace_minutes: definition.misfire_grace_minutes || 30
  };
}

function truncate(value: string, size = 16) {
  return value.length > size ? `${value.slice(0, size)}...` : value;
}

function safePathLabel(value: string) {
  if (!value) {
    return "-";
  }
  const normalized = value.replace(/\\/g, "/");
  const filename = normalized.split("/").filter(Boolean).pop();
  if (!filename) {
    return "local evidence artifact";
  }
  if (/^[A-Za-z]:/.test(value) || normalized.startsWith("/") || normalized.includes("/Users/")) {
    return filename;
  }
  return filename;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(new Date(value));
}

function formatAge(seconds: number) {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return `${hours}h`;
  }
  return `${Math.floor(hours / 24)}d`;
}

createRoot(document.getElementById("root")!).render(<App />);
