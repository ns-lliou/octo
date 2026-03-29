# 🐙 Octo

SWG Internal tooling for managing backend configurations across environments.

## Features

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

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the app:**
```bash
streamlit run src/Home.py
```

## Project Structure

```
src/
├── Home.py                            # Landing page
├── pages/
│   ├── 1_Client_Feature_Flag.py      # Client feature flag management
│   ├── 2_DP_Tenant_Feature_Flag.py   # DataPlane tenant feature flag management
│   ├── 3_Show_Tenant_List.py         # Tenant list viewer with search/filter
│   ├── 4_Query_RIS_Reference.py      # RIS reference query (object consumer / config object)
│   └── 5_Manage_API_Token.py         # API token lifecycle management (generate / revoke)
├── api/
│   ├── client_feature_flag.py        # API client for client feature flags
│   ├── dp_tenant_feature_flag.py     # API client for DP tenant feature flags
│   ├── get_all_tenants_in_stack.py   # API client for tenant list
│   ├── ris_base.py                   # API client for RIS (object consumers & config objects)
│   └── scim_me.py                    # API client for SCIM Me (get user, generate/revoke token)
├── components/
│   └── webui_login.py                # Reusable web UI login widget (session-based auth)
└── config/
    ├── paths.py                       # Base directory resolution
    └── stacks.json                    # Environment stack configuration
```
