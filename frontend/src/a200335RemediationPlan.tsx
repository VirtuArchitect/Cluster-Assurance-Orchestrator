import React from "react";

export function A200335RemediationPlan() {
  return <section className="panel remediation-plan" aria-label="A200335 remediation plan">
    <h3>Remediation plan · PE network prerequisites</h3>
    <p className="monitoring-warning"><strong>Operator guidance only.</strong> This plan allocates no addresses, changes no settings and executes no tasks. An authorized administrator must use an approved change and the installed-release procedure.</p>
    <p>Start from fresh deployment evidence above. A historical failure, an unset VIP or a resolved alert alone does not establish the current blocker or recovery. Cluster FQDN configuration remains unverified unless independently checked.</p>

    <h4>Values to approve before starting</h4>
    <div className="monitoring-table-wrap"><table className="monitoring-table"><thead><tr><th>Planned value</th><th>Selection and validation</th></tr></thead><tbody>
      <tr><td><code>&lt;PE_CLUSTER_VIP&gt;</code></td><td>Reserve an unused address in the verified CVM management subnet. Validate IPAM, DHCP exclusions and network ownership; a failed ping alone does not prove availability.</td></tr>
      <tr><td><code>&lt;PE_DATA_SERVICES_IP&gt;</code></td><td>Reserve a different unused address in the installed release's supported CVM eth0 subnet. Check dependent services and routing.</td></tr>
      <tr><td><code>&lt;PE_CLUSTER_FQDN&gt;</code></td><td>If required, approve the cluster DNS name and supported PE configuration. Normally resolve it to the cluster VIP; verify DNS and certificate-name compatibility from PC and administrator networks.</td></tr>
    </tbody></table></div>
    <p>Placeholders are not proposed or reserved addresses. Do not reuse a CVM, hypervisor, PC, gateway or another device's address. Do not change CVM/host addressing or cluster registration as part of this plan.</p>

    <details open><summary>1. Prerequisite checks and change preparation</summary>
      <ul>
        <li>Confirm the affected PC and PE identities, installed AOS/PC/NCC versions, current failed task/precheck and fresh prerequisite values. Independently inspect cluster FQDN configuration.</li>
        <li>Record existing VIP, Data Services IP, subnet/mask, gateway, DNS, task IDs and alert evidence. Retain the prior configuration, including unset values.</li>
        <li>Obtain address/DNS approval and identify Volumes, Files, Objects, CMSP or other consumers. Confirm their service checks and rollback owners.</li>
        <li>Verify cluster resiliency, stable PC authentication, management reachability and independent PE/CVM and VM-console access. Review PC resource/sizing warnings against the installed release.</li>
      </ul>
      <p><strong>Proceed when:</strong> addresses and dependencies are validated, access is recoverable, and the change owner has approved the release-specific procedure.</p>
      <p><strong>Stop when:</strong> address ownership, subnet, dependencies, health or the supported procedure is unclear. Resolve those gaps before changing anything.</p>
    </details>
    <details><summary>2. Configure and validate the PE cluster VIP</summary>
      <p>During the approved change window, configure only the approved cluster VIP through the installed-version PE cluster-details/network procedure. Preserve existing direct PE access.</p>
      <ul><li>Confirm the value persists in PE and the read-only cluster API.</li><li>Verify authenticated HTTPS access through the VIP from PC and an administrator workstation.</li><li>Check for duplicate-address symptoms, lost management access and new cluster alerts before proceeding.</li></ul>
      <p><strong>Stop:</strong> duplicate addressing, unexpected reachability changes or management loss. Do not proceed to the next setting.</p>
    </details>
    <details><summary>3. Validate optional cluster FQDN and DNS</summary>
      <p>If using the FQDN route or an organizational requirement, configure the supported PE setting and approved DNS records. A DNS record alone does not prove that PE's required FQDN setting is configured.</p>
      <ul><li>Verify name resolution from PC and administrator networks; check reverse records where policy requires them.</li><li>Verify the expected VIP is returned and authenticated HTTPS works with appropriate certificate names and trust.</li><li>Retain existing management access. Do not bypass TLS validation or re-register the cluster to make a test pass.</li></ul>
      <p><strong>Stop:</strong> incorrect DNS, certificate mismatch or loss of authenticated access.</p>
    </details>
    <details><summary>4. Configure and validate the PE Data Services IP</summary>
      <p>Configure the separately approved Data Services IP through the supported PE procedure only after prior checks pass.</p>
      <ul><li>Confirm the setting persists in PE and the read-only cluster API.</li><li>Verify network ownership, reachability and the actual dependent services.</li><li>Check existing consumers remain operational. Test iSCSI discovery only where applicable; ping or an open port alone does not establish service health.</li></ul>
      <p><strong>Stop:</strong> duplicate addressing, dependency failures or unexpected service impact. Do not continue into deployment recovery.</p>
    </details>
    <details><summary>5. Recover deployment through the supported procedure</summary>
      <p>Refresh task evidence first. A RUNNING parent with a FAILED precheck is not successful deployment. Confirm whether the task is failed, still running or stuck before any retry.</p>
      <ul><li>Use the version-specific supported recovery/precheck procedure; engage Nutanix Support for a stuck task.</li><li>Confirm the VIP/FQDN and Data Services IP precheck errors disappear before continuing.</li><li>Verify deployment and relevant component-health checks complete successfully. Do not repeatedly enable/redeploy the platform, cancel tasks, delete pods or restart services as a shortcut.</li></ul>
      <p><strong>Stop:</strong> a running/stuck operation, recurring precheck failure, new errors or unclear recovery instructions.</p>
    </details>
    <details><summary>6. Acceptance and post-change monitoring</summary>
      <ul><li>Approved network settings persist, DNS/trust tests pass and dependent services work.</li><li>Prechecks pass, deployment completes and independent microservices diagnostics report healthy components.</li><li>Previously affected PC functions and workload/service impact are validated by the operator.</li><li>Fresh PC/PE collection succeeds. A200335 resolves in Prism and the app no longer confirms the prerequisite blocker.</li><li>Observe for recurrence during the agreed monitoring window and retain before/after evidence.</li></ul>
      <p>Address changes, a successful API request or alert resolution alone are insufficient. The app records no operator recovery sign-off through this plan.</p>
    </details>
    <details><summary>Rollback and escalation guidance</summary>
      <p><strong>Before dependent deployment begins:</strong> stop at the failed validation stage. If the supported procedure permits it and dependency checks confirm safety, revert only newly introduced VIP/Data Services IP and DNS settings to the recorded prior configuration. Preserve direct PE and console access, then revalidate baseline services.</p>
      <p><strong>After CMSP or another consumer uses the new addresses:</strong> do not simply clear the addresses or DNS records. Obtain dependency-aware rollback/recovery guidance from Nutanix Support and the affected service owners.</p>
      <p><strong>Escalate:</strong> management loss, address conflicts, service disruption, stuck deployment, recurring failures or uncertain ownership. Supply cluster/task/alert IDs, exact versions, timestamps, approved values and before/after diagnostic evidence. No rollback runs from this view.</p>
    </details>
    <p className="remediation-reference">Procedure reference: <a href="https://www.nutanix.com/content/dam/nutanix/documents/certifications/prism-element-web-console-guide.pdf" target="_blank" rel="noreferrer">Nutanix Prism Element Web Console Guide</a>. Verify instructions against the installed release before implementation.</p>
  </section>;
}
