# 🐙 Octo

Internal tooling for managing backend configurations across environments.

## Features

### Client Feature Flags
Get and set client (tenant-level) feature flags via the provisioner API. Supports searching across all flags for a given tenant in any environment.

### DataPlane Tenant Feature Flags
Get and set DataPlane tenant feature flags via the provisioner API. The Set operation accepts a freeform JSON body (with basic validation) to update one or more flags at once.

### Show Tenant List
Browse all tenants in a stack environment. Tenant data is fetched from the provisioner API and cached per environment for the session. Supports filtering by Tenant ID, name, hostname, or description, with full JSON detail shown for matched tenants.

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
│   └── 3_Show_Tenant_List.py         # Tenant list viewer with search/filter
├── api/
│   ├── client_feature_flag.py        # API client for client feature flags
│   ├── dp_tenant_feature_flag.py     # API client for DP tenant feature flags
│   └── get_all_tenants_in_stack.py   # API client for tenant list
└── config/
    ├── paths.py                       # Base directory resolution
    └── stacks.json                    # Environment stack configuration
```
