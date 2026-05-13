# 🐙 Octo

SWG internal tooling for managing backend configurations across environments.

## Features

### Create Tenant
Provision new tenants on QA01 or STG01 via `tsh ssh`. Executes all provisioning steps sequentially: (1) create org, (2) refresh cluster mapping, (3) sync DNS via Polaris GSLB, (4) send admin verification email via MS Platform. Supports **Single** and **Batch** modes.

- **Preflight confirmation** — before any provisioning runs, a confirmation panel displays the stack, knode, and full request payload(s) for review. The Run button is disabled while the panel is open.
- **Batch mode** — all tenant creates run first, then a single cluster mapping refresh, then per-tenant DNS + email. Deduplicates cluster mapping and admin UUID lookups across tenants.
- **Incomplete handling** — if the provisioner returns `status: incomplete` (partial success), the step is marked with `⚠️`, remediation curl commands are displayed, and the overall status is shown as `incomplete` rather than `success`.
- **Elapsed time** — each result shows total provisioning time (e.g. `8m 6s`) to help track slow environments.
- Failed tenants do not block the rest of the batch. All run results are auto-saved to `artifacts/` and available for download.

> **Note:** There is currently no in-app way to resume or retry individual provisioning steps for a failed or incomplete tenant. Remediation steps (where available) must be run manually on the knode or Provisioner hosts. Per-step retry pages are on the roadmap.

### Client Feature Flags
Get and set client (tenant-level) feature flags via the provisioner API. Supports searching across all flags for a given tenant in any environment.

### DataPlane Tenant Feature Flags
Get and set DataPlane tenant feature flags via the provisioner API. The Set operation accepts a freeform JSON body (with basic validation) to update one or more flags at once.

### Show Tenant List
Browse all tenants in a stack environment. Tenant data is fetched from the provisioner API and cached per environment for the session. Supports filtering by Tenant ID, name, hostname, or description, with full JSON detail shown for matched tenants.

### Query RIS Reference
Inspect reference relations between **object consumers** and **config objects** in the Referential Integrity Service (RIS). The page displays two side-by-side panels — one per entity type — each supporting a **List** operation (browse all entries by name) and a **Get by ID** operation (drill into a specific entry's references). Query results persist in the session so both sides can be observed simultaneously.

### Manage API Token
Generate or revoke the API token for a tenant web UI user. Requires logging in to the tenant web UI via the built-in **Web UI Login** widget (sidebar). Displays current token status (active/none) with issued and expiry timestamps in local time. Generated tokens are shown once and must be copied immediately — they are not retrievable after leaving the page.

## Getting Started

**Prerequisites:** Python 3.10 or higher.
- macOS: `brew install python@3.11`
- Windows: [python.org/downloads](https://www.python.org/downloads/)

**Run the app:**

macOS/Linux:
```bash
./run.sh
```

Windows (PowerShell):
```powershell
.\run.ps1
```

The script creates a virtual environment, installs dependencies, and launches the app automatically.

## Project Structure

```
src/
├── Home.py                            # App entry point and navigation router
├── pages/
│   ├── home.py                        # Landing page
│   ├── create_tenant.py               # Tenant provisioning (single + batch, tsh ssh)
│   ├── show_tenant_list.py            # Tenant list viewer with search/filter
│   ├── client_feature_flag.py         # Client feature flag management
│   ├── dp_tenant_feature_flag.py      # DataPlane tenant feature flag management
│   ├── query_ris_reference.py         # RIS reference query (object consumer / config object)
│   └── manage_api_token.py            # API token lifecycle management (generate / revoke)
├── api/
│   ├── tenant_provisioner.py          # Tenant provisioning via tsh ssh (create, DNS, email)
│   ├── client_feature_flag.py         # API client for client feature flags
│   ├── dp_tenant_feature_flag.py      # API client for DP tenant feature flags
│   ├── get_all_tenants_in_stack.py    # API client for tenant list
│   ├── ris_base.py                    # API client for RIS (object consumers & config objects)
│   └── scim_me.py                     # API client for SCIM Me (get user, generate/revoke token)
├── components/
│   └── webui_login.py                 # Reusable web UI login widget (session-based auth)
└── config/
    ├── paths.py                        # Base directory resolution
    └── stacks.json                     # Environment stack configuration (incl. knodes)
artifacts/                             # Auto-saved provisioning run results (gitignored)
```
