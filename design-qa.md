# Design QA

## Login Option

- Reference: user-provided ZTF-Orchestrator login screenshot.
- Implementation: `frontend/src/main.tsx` and `frontend/src/styles.css`.
- Result: matched the ZTF suite login structure with a centered light card, shared logo mark, large product title, muted subtitle, sign-in form, focus ring, primary sign-in action, access note, and footer link treatment.
- Product adaptation: title and subtitle use `Cluster Assurance` and `Orchestrator for Nutanix Environments`.
- Interaction check: entered dummy credentials, toggled password visibility, signed in to the dashboard, and signed out back to the login page.
- Accessibility check: login form exposes username and password fields, named show password control, submit button, and alert text for missing credentials.
- Residual note: authentication is currently a frontend session gate only; server-side identity, persistent sessions, and RBAC enforcement should be handled in the backend auth phase.
