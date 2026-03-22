# 🐙 Octo

Internal tooling for managing backend configurations across environments.

## Features

### Client Feature Flags
Get and set client (tenant-level) feature flags via the provisioner API. Supports searching across all flags for a given tenant in any environment.

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
├── Home.py                        # Landing page
├── pages/
│   └── 1_Client_Feature_Flag.py  # Client feature flag management
├── api/
│   └── client_feature_flag.py    # API client for client feature flags
└── config/
    ├── paths.py                   # Base directory resolution
    └── stacks.json                # Environment stack configuration
```
