# Local Prism certificate trust

Place an independently verified PEM CA certificate/bundle here. Files other than this README are ignored by Git and excluded from Docker builds. Do not put private keys here.

Compose mounts this directory read-only at `/etc/cao-trust` for the API and worker. Set `CAO_CUSTOM_CA_BUNDLE=/etc/cao-trust/prism-ca.pem` in local `config/appliance.env`, then recreate both services. Set each saved Prism connection to strict TLS and test it before collecting fresh evidence. Custom CAs supplement the system trust store; hostname/IP, chain and expiry verification remain enabled. Missing/invalid trust must fail rather than falling back to insecure mode.

Obtain trust anchors through an authenticated administrative source. Do not install an unauthenticated peer certificate as trusted merely because the endpoint presented it. Update/rotate the local trust bundle through your approved procedure. Local trust configuration does not certify production readiness.
