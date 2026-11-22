# Verified Prism TLS

The API and unattended worker share `prism_ssl_context`. Strict mode keeps certificate-chain, expiry and hostname/IP verification enabled. An independently verified private CA supplements the operating-system trust store; it does not disable identity checks.

## Local configuration

1. Obtain the issuing CA through an authenticated administrative source. Validate its provenance and fingerprint independently of the unauthenticated Prism endpoint. Do not trust an arbitrary downloaded leaf certificate or copy private keys.
2. Put the PEM CA/bundle in local `config/trust/prism-ca.pem`. Git ignores local trust material and Docker builds exclude it. The appliance bundle includes only the generic trust README, never these local certificates.
3. In private `config/appliance.env`, set `CAO_CUSTOM_CA_BUNDLE=/etc/cao-trust/prism-ca.pem` and `CAO_TLS_MODE=strict`. Compose mounts `config/trust` read-only for the API and worker. Recreate both services so they load the configuration.
4. Set each saved PE/PC connection to strict TLS, preserving its endpoint and credentials. Test each connection, then obtain new inventory and monitoring evidence. Historical TLS-unverified evidence is not relabelled.
5. Verify worker readiness, feed completeness, inventory confidence and strict TLS in the dashboard. Source alerts and incomplete recovery still require operational triage; TLS verification does not establish infrastructure health or production acceptance.

Connection tests use the PE cluster-details GET or PC cluster-list read-only POST, with the same CA trust as collectors. Missing/invalid trust or a failed chain/name/expiry check must fail closed. There is no automatic insecure fallback. The custom CA file must remain available to both services after recreation; do not rely on copying files into a temporary container filesystem.

## Rotation and acceptance

Maintain ownership, expiry review and approved renewal for the trust bundle and target certificates. Before replacing a CA, validate the new trust and endpoint identities. Never silently re-enable TLS bypass as a recovery shortcut. This application does not change PE/PC certificates, DNS, VIPs, infrastructure trust stores or server-side settings.

Tests generate synthetic local CA/server certificates in temporary directories. Positive checks validate both probe and collector paths; negative checks reject an untrusted CA, expired certificate, wrong hostname and missing/invalid trust before authenticated HTTP requests reach the test server. OpenSSL is an authoring/test tool only; no runtime dependency was added.
