# Lab Validation Plan

## Purpose

Validate Cluster Assurance Orchestrator against the lab without turning the first build into an unbounded infrastructure tool. The first lab phase proves read-only Prism access, version discovery, inventory collection, status handling, audit events and evidence packaging.

## Lab Endpoints

| Endpoint | URL | Validation posture |
| --- | --- | --- |
| Prism Central | `https://192.0.2.205:9440/` | Read-only API discovery first |
| Prism Element | `https://192.0.2.201:9440/` | Read-only fallback discovery first |

Credentials must remain in local ignored configuration only. Use `config/local.env` for local testing and keep `config/local.env.example` as the committed template.

## Recommended Validation Sequence

1. **Configuration loading**
   - Load endpoint URLs, credential references and TLS mode from local configuration.
   - Refuse to start lab validation if credentials are missing.
   - Do not print passwords, tokens, cookies or full authorization headers.

2. **Connectivity and TLS**
   - Attempt Prism Central and Prism Element HTTPS reachability.
   - In `strict` TLS mode, reject invalid certificates.
   - In `insecure_skip_verify` mode, mark every result as lab-only and non-production.
   - Record endpoint, timestamp, TLS mode and outcome in evidence.

3. **Authentication**
   - Authenticate using local lab credentials.
   - Store only session metadata needed for the current process.
   - Confirm failed authentication produces `UNKNOWN`, not `HEALTHY`.

4. **Version and capability discovery**
   - Discover Prism Central and Prism Element versions.
   - Record supported API roots and capability gaps.
   - Update the capability matrix before adding adapter methods.

5. **Inventory read**
   - Retrieve clusters and nodes using documented Prism APIs only.
   - Preserve raw response artifacts outside normal logs.
   - Normalize inventory into internal models with source and collection timestamp.

6. **Health rule smoke test**
   - Run the initial read-only health checks:
     - endpoint reachability
     - authentication
     - version discovery
     - inventory freshness
     - cluster availability where supported by documented API
   - Missing or unparsable mandatory data must produce `UNKNOWN`.

7. **Evidence package**
   - Write a local run manifest containing:
     - product version
     - endpoint aliases
     - profile version
     - collector timestamps
     - normalized result summary
     - raw artifact references
     - SHA-256 hashes
   - Keep raw payloads out of application logs.

8. **Operator review**
   - Review the result summary, unknown states, stale states and raw artifact links.
   - Confirm no UI or report implies Nutanix support, certification or endorsement.

## NCC and SSH Gate

Do not enable NCC or SSH in the first lab pass. NCC may be introduced only after:

- API inventory and evidence packaging work reliably.
- The command allowlist is committed and reviewed.
- The selected command profile is environment-approved.
- The target CVM selection rule is implemented without fixed host assumptions.
- Unknown NCC output is covered by parser tests and cannot be classified as healthy.

## Credential Note

The lab credentials shared for this validation should be rotated after initial testing if the lab remains in active use.
