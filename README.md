# 🐙 Octo

Internal tooling for managing backend configurations across environments.

## Features

### Client Feature Flags
Get and set client (tenant-level) feature flags via the provisioner API. Supports searching across all flags for a given tenant in any environment.

### DataPlane Tenant Feature Flags
Get and set DataPlane tenant feature flags via the provisioner API. The Set operation accepts a freeform JSON body (with basic validation) to update one or more flags at once.

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
│   └── 2_DP_Tenant_Feature_Flag.py   # DataPlane tenant feature flag management
├── api/
│   ├── client_feature_flag.py        # API client for client feature flags
│   └── dp_tenant_feature_flag.py     # API client for DP tenant feature flags
└── config/
    ├── paths.py                       # Base directory resolution
    └── stacks.json                    # Environment stack configuration
```
