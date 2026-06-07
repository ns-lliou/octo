import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from api import APIRequestError, APIResponseError
from api.admin_activator import activate_admin_mariadb, activate_admin_postgres, is_aws_migrated, db_credentials_file_exists
from api.tenant_provisioner import (
    create_tenant,
    get_admin_uuid,
    ping_knode,
    refresh_cluster_mapping,
    send_verification_email,
    sync_dns,
)
from config.paths import BASE_DIR
from config.stacks import get_knode_stacks

ARTIFACTS_DIR = BASE_DIR.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

KNODE_STACKS = get_knode_stacks()

st.set_page_config(page_title="Create Tenant", layout="wide")
st.title("Create Tenant")
st.markdown("""
Provision one or more tenants on **QA01** or **STG01** via `tsh ssh`. All provisioner API calls
execute on the selected knode — no KLBI/ingress involved.

- **Single mode** — fill the form, click **Run**.
- **Batch mode** — paste a JSON array of tenant definitions, click **Run Batch**.

Results are auto-saved to `artifacts/` and available for download.
""")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    env = st.selectbox("Stack", list(KNODE_STACKS.keys()))
    stack = KNODE_STACKS[env]
    knode = st.selectbox("Knode", stack["knodes"])
    st.caption("Only QA01 and STG01 are supported for tenant provisioning via knode. Other stacks (Hippo, FedRAMP, etc.) use different provisioning paths not covered here.")
    mode = st.radio("Mode", ["Single", "Batch"])
    st.divider()
    st.caption(f"GSLB home_pop: `{stack['gslb_home_pop']}`")
    st.caption(f"Domain base: `{stack['stack_fqdn_base']}`")
    st.caption(f"MS Platform: `{stack['ms_platform_fqdn']}`")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fmt_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    return f"{seconds // 60}m {seconds % 60}s"


def _make_fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]


def _clear_preflight() -> None:
    st.session_state.pop("_preflight_pending", None)
    st.session_state.pop("_preflight_fingerprint", None)


def _build_fqdn(hostname: str, fqdn_base: str) -> str:
    """Build tenant FQDN: hostname.fqdn_base, stripping any existing suffix."""
    hostname = hostname.strip().rstrip(".")
    if hostname.endswith(f".{fqdn_base}"):
        return hostname
    return f"{hostname}.{fqdn_base}"


def _build_payload(td: dict[str, Any], fqdn_base: str) -> dict[str, Any]:
    """Build the create_tenant API payload from a tenant definition dict."""
    domains = (
        [d.strip() for d in td.get("domains", fqdn_base).split(",") if d.strip()]
        if isinstance(td.get("domains"), str)
        else td.get("domains", [fqdn_base])
    )
    return {
        "orgName": td["orgName"],
        "orgDesc": td.get("orgDesc", td["orgName"]),
        "country": td.get("country", "US"),
        "location": td.get("location", "SantaClara"),
        "state": td.get("state", "CA"),
        "hostname": td["hostname"].strip(),
        "custFName": td["custFName"],
        "custLName": td["custLName"],
        "adminEmail": td["adminEmail"],
        "dpIP": "",
        "iswiyc": "0",
        "domains": domains,
        "industry": td.get("industry", "7372"),
        "paid": td.get("paid", "0"),
        "seats": td.get("seats", "10"),
        "url_filtering_enabled": "1",
        "fed_ramp_tenant": td.get("fed_ramp_tenant", "0"),
    }


def _activate_admin(env: str, stack: dict, admin_uuid: str, admin_email: str, tenant_hostname: str, admin_password: str) -> dict[str, Any]:
    """Detect AWS-migration status and run the correct Step 5 activation path."""
    mariadb_host = stack.get("mariadb_host", "")
    if not mariadb_host:
        raise APIRequestError(f"No mariadb_host configured for stack '{env}' in stacks.json")

    migrated = is_aws_migrated(env, mariadb_host, tenant_hostname)
    if migrated:
        return activate_admin_postgres(env, admin_uuid, admin_password)
    else:
        return activate_admin_mariadb(env, mariadb_host, tenant_hostname, admin_email, admin_password)


def _save_artifact(results: list[dict[str, Any]], env: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ARTIFACTS_DIR / f"create_tenant_{env}_{ts}.json"
    path.write_text(json.dumps(results, indent=2))
    return path


def _run_single(knode: str, stack: dict, env: str, payload: dict[str, Any], admin_email: str, admin_password: str = "") -> dict[str, Any]:
    """Execute all 4 provisioning steps for one tenant. Returns a result record."""
    result: dict[str, Any] = {
        "hostname": payload.get("hostname"),
        "admin_email": admin_email,
        "env": env,
        "knode": knode,
        "request_payload": payload,
        "steps": {},
        "tenant_id": None,
        "fqdn": None,
        "overall_status": "incomplete",
    }

    # Step 1: Create tenant
    step1_incomplete = False
    t0 = time.time()
    try:
        data = create_tenant(knode, payload)
        result["steps"]["1_create_tenant"] = {"status": "ok", "response": data}
        result["tenant_id"] = (
            data.get("tenantData", {}).get("TenantID")
            or data.get("tenantId")
            or data.get("tenant_id")
            or data.get("orgId")
        )
        result["fqdn"] = (
            data.get("tenantData", {}).get("ui_hostname")
            or data.get("hostname")
            or data.get("fqdn")
        )
        step1_status = (data.get("status") or "").lower()
        if step1_status != "success":
            msg = data.get("msg") or data.get("message") or "status is not 'success'"
            result["steps"]["1_create_tenant"]["warning"] = msg
            result["steps"]["1_create_tenant"]["remediation_steps"] = (
                data.get("remediationSteps") or data.get("remediation_steps")
            )
            step1_incomplete = True
    except (APIRequestError, APIResponseError) as e:
        result["steps"]["1_create_tenant"] = {"status": "error", "error": str(e)}
        result["overall_status"] = "failed_at_step_1"
        return result

    if not result["tenant_id"]:
        if "warning" not in result["steps"]["1_create_tenant"]:
            result["steps"]["1_create_tenant"]["warning"] = "tenant_id not found in response — cannot continue"
        result["overall_status"] = "failed_at_step_1"
        return result

    tenant_id = str(result["tenant_id"])
    fqdn = result["fqdn"] or _build_fqdn(payload["hostname"], stack["stack_fqdn_base"])

    # Step 2: Refresh cluster mapping
    try:
        data = refresh_cluster_mapping(knode)
        result["steps"]["2_cluster_mapping"] = {"status": "ok", "response": data}
    except (APIRequestError, APIResponseError) as e:
        result["steps"]["2_cluster_mapping"] = {"status": "error", "error": str(e)}
        result["overall_status"] = "failed_at_step_2"
        return result

    # Step 3: Sync DNS
    try:
        data = sync_dns(knode, fqdn, stack["gslb_home_pop"])
        result["steps"]["3_dns_sync"] = {"status": "ok", "response": data}
    except (APIRequestError, APIResponseError) as e:
        result["steps"]["3_dns_sync"] = {"status": "error", "error": str(e)}
        result["overall_status"] = "failed_at_step_3"
        return result

    # Step 4a: Get admin UUID (email-scoped, consistent across tenants)
    admin_uuid = st.session_state.get("_admin_uuid_cache", {}).get(admin_email)
    if not admin_uuid:
        try:
            admin_uuid = get_admin_uuid(knode, stack["ms_platform_fqdn"], admin_email, tenant_id)
            if "_admin_uuid_cache" not in st.session_state:
                st.session_state["_admin_uuid_cache"] = {}
            st.session_state["_admin_uuid_cache"][admin_email] = admin_uuid
            result["steps"]["4a_get_admin_uuid"] = {"status": "ok", "uuid": admin_uuid}
        except (APIRequestError, APIResponseError) as e:
            result["steps"]["4a_get_admin_uuid"] = {"status": "error", "error": str(e)}
            result["overall_status"] = "failed_at_step_4a"
            return result
    else:
        result["steps"]["4a_get_admin_uuid"] = {"status": "ok_cached", "uuid": admin_uuid}

    # Step 4b: Send verification email (skipped when admin_password is set — SQL activation replaces it)
    if admin_password:
        result["steps"]["4b_send_verification_email"] = {"status": "skipped", "note": "SQL activation will be used instead"}
    else:
        try:
            data = send_verification_email(knode, stack["ms_platform_fqdn"], admin_uuid, tenant_id)
            result["steps"]["4b_send_verification_email"] = {"status": "ok", "response": data}
        except (APIRequestError, APIResponseError) as e:
            err_str = str(e)
            # 400 "already verified" is not a real failure — tenant is usable
            if "already verified" in err_str.lower():
                result["steps"]["4b_send_verification_email"] = {"status": "already_verified", "note": err_str}
            else:
                result["steps"]["4b_send_verification_email"] = {"status": "error", "error": err_str}
                result["overall_status"] = "failed_at_step_4b"
                return result

    # Step 5: Activate admin via SQL (auto-detects Postgres vs MariaDB path)
    if admin_password:
        try:
            data = _activate_admin(env, stack, admin_uuid, admin_email, payload["hostname"], admin_password)
            result["steps"]["5_activate_admin"] = {"status": "ok", "response": data}
        except (APIRequestError, APIResponseError) as e:
            result["steps"]["5_activate_admin"] = {"status": "error", "error": str(e)}
            result["overall_status"] = "failed_at_step_5"
            return result

    result["overall_status"] = "incomplete" if step1_incomplete else "success"
    result["elapsed_seconds"] = round(time.time() - t0)
    return result


def _display_result(result: dict[str, Any], index: int | None = None) -> None:
    label = result.get("hostname") or f"Tenant #{index}"
    status = result.get("overall_status", "unknown")

    icon = {"success": "✅", "incomplete": "⚠️"}.get(status, "❌") if "failed" not in status else "❌"
    if status == "success":
        icon = "✅"
    elif "failed" in status:
        icon = "❌"
    else:
        icon = "⚠️"

    with st.expander(f"{icon} {label} — {status}", expanded=(status != "success")):
        col1, col2, col3 = st.columns(3)
        col1.write(f"**Tenant ID:** `{result.get('tenant_id') or '—'}`")
        col2.write(f"**FQDN:** `{result.get('fqdn') or '—'}`")
        elapsed = result.get("elapsed_seconds")
        col3.write(f"**Total time:** `{_fmt_elapsed(elapsed)}`" if elapsed is not None else "")

        for step_key, step_data in result.get("steps", {}).items():
            step_status = step_data.get("status", "unknown")
            step_icon = "⚠️" if "warning" in step_data else ("✅" if step_status in ("ok", "ok_cached", "already_verified") else ("⏭️" if step_status == "skipped" else "❌"))
            st.markdown(f"**{step_icon} {step_key}**")

            if step_status == "error":
                st.error(step_data.get("error"))
            if step_status == "skipped":
                st.caption(step_data.get("note", "Skipped"))
            if step_status == "already_verified":
                st.info(step_data.get("note"))
            if "warning" in step_data:
                st.warning(step_data["warning"])
            if "remediation_steps" in step_data and step_data["remediation_steps"]:
                st.markdown("**Remediation steps:**")
                remediation = step_data["remediation_steps"]
                if isinstance(remediation, list):
                    for s in remediation:
                        st.code(s)
                else:
                    st.code(str(remediation))
            if "response" in step_data:
                st.json(step_data["response"], expanded=False)
            if "uuid" in step_data:
                st.write(f"UUID: `{step_data['uuid']}`")


# ── Preflight inline confirmation ──────────────────────────────────────────────
def _preflight_confirm_section(pending: dict) -> None:
    """Render an inline confirmation panel. Confirm/Cancel both do st.rerun()."""
    mode = pending.get("mode")
    st.divider()
    st.subheader("Confirm Provisioning")
    col_info, col_buttons = st.columns([3, 1])
    with col_info:
        st.markdown(f"**Stack:** `{pending.get('env')}` &nbsp; **Knode:** `{pending.get('knode')}`")
        if mode == "Single":
            p = pending.get("payload", {})
            st.markdown(f"**Hostname:** `{p.get('hostname')}.{pending.get('fqdn_base')}`")
            st.markdown(f"**Org Name:** {p.get('orgName')}  \n**Admin Email:** {p.get('adminEmail')}")
            with st.expander("Request payload (tenant-provisioner/rest/create/org)"):
                st.json(p)
        else:
            payloads = pending.get("payloads", [])
            est_min = len(payloads) * 6
            est_max = len(payloads) * 8
            st.markdown(f"**{len(payloads)} tenant(s)** — estimated {est_min}–{est_max} minutes total")
            rows = [
                {"#": i + 1, "Hostname": p["hostname"], "Org Name": p["orgName"], "Admin Email": p["adminEmail"]}
                for i, p in enumerate(payloads)
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            with st.expander("Request payloads (tenant-provisioner/rest/create/org)"):
                st.json(payloads)
        st.warning("This will create real tenants. This action cannot be undone from Octo.")
    with col_buttons:
        st.write("")
        if st.button("Confirm", type="primary", use_container_width=True):
            st.session_state["_preflight_running_data"] = st.session_state.pop("_preflight_pending")
            st.rerun()
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_preflight_pending", None)
            st.rerun()
    st.divider()


# ── Single mode ────────────────────────────────────────────────────────────────
if mode == "Single":
    # Clear any stale Batch preflight when switching modes
    if st.session_state.get("_preflight_pending", {}).get("mode") == "Batch":
        _clear_preflight()

    st.subheader("Tenant Definition")
    col1, col2 = st.columns(2)
    with col1:
        hostname = st.text_input("Hostname", placeholder="my-tenant-01", help="Unique short hostname. FQDN will be built automatically.")
        org_name = st.text_input("Org Name", placeholder="My Tenant Org")
        admin_email = st.text_input("Admin Email", placeholder="you@netskope.com")
    with col2:
        cust_fname = st.text_input("First Name", placeholder="John")
        cust_lname = st.text_input("Last Name", placeholder="Doe")
        domains_input = st.text_input("Domains (comma-separated)", value=stack["stack_fqdn_base"])

    admin_password = st.text_input(
        "Admin Password (optional)",
        placeholder="Leave blank to send verification email instead",
        type="password",
        help="If provided, the admin account is activated directly via SQL — no email click required. Leave blank to use the standard email verification flow.",
    )

    with st.expander("Advanced / Optional fields"):
        org_desc = st.text_input("Org Description", value="SWG QE")
        country = st.text_input("Country", value="US")
        location = st.text_input("Location", value="SantaClara")
        state_input = st.text_input("State", value="CA")
        industry = st.text_input("Industry (SIC code)", value="7372")
        paid = st.selectbox("Paid", ["0", "1"], index=0)
        seats = st.text_input("Seats", value="10")
        fed_ramp = st.selectbox("FedRAMP Tenant", ["0", "1"], index=0)

    # Detect stale preflight before rendering the Run button so it re-enables immediately
    if st.session_state.get("_preflight_pending", {}).get("mode") == "Single":
        current_fp = _make_fingerprint({
            "mode": "Single", "env": env, "knode": knode,
            "hostname": hostname.strip(), "org_name": org_name,
            "admin_email": admin_email, "cust_fname": cust_fname,
            "cust_lname": cust_lname, "domains": domains_input,
            "org_desc": org_desc, "country": country, "location": location,
            "state": state_input, "industry": industry, "paid": paid,
            "seats": seats, "fed_ramp": fed_ramp, "has_password": bool(admin_password),
        })
        if current_fp != st.session_state.get("_preflight_fingerprint"):
            _clear_preflight()
            st.warning("Inputs changed after preflight review — please click Run again to review the updated payload.")

    run_clicked = st.button("Run", type="primary", disabled=bool(st.session_state.get("_preflight_pending") or st.session_state.get("_preflight_running_data")))

    if run_clicked:
        errors = []
        if not hostname:
            errors.append("Hostname is required.")
        if not org_name:
            errors.append("Org Name is required.")
        if not admin_email:
            errors.append("Admin Email is required.")
        if not cust_fname or not cust_lname:
            errors.append("First and Last Name are required.")
        if admin_password and not db_credentials_file_exists():
            errors.append("Admin Password is set but db_credentials.json is missing — copy src/config/db_credentials.json.example to db_credentials.json and fill in credentials.")
        if errors:
            _clear_preflight()
            for e in errors:
                st.error(e)
            st.stop()

        fqdn = _build_fqdn(hostname, stack["stack_fqdn_base"])
        domains = [d.strip() for d in domains_input.split(",") if d.strip()]
        payload = {
            "orgName": org_name,
            "orgDesc": org_desc or org_name,
            "country": country,
            "location": location,
            "state": state_input,
            "hostname": hostname.strip(),
            "custFName": cust_fname,
            "custLName": cust_lname,
            "adminEmail": admin_email,
            "dpIP": "",
            "iswiyc": "0",
            "domains": domains,
            "industry": industry,
            "paid": paid,
            "seats": seats,
            "url_filtering_enabled": "1",
            "fed_ramp_tenant": fed_ramp,
        }
        fp = _make_fingerprint({
            "mode": "Single", "env": env, "knode": knode,
            "hostname": hostname.strip(), "org_name": org_name,
            "admin_email": admin_email, "cust_fname": cust_fname,
            "cust_lname": cust_lname, "domains": domains_input,
            "org_desc": org_desc, "country": country, "location": location,
            "state": state_input, "industry": industry, "paid": paid,
            "seats": seats, "fed_ramp": fed_ramp, "has_password": bool(admin_password),
        })
        st.session_state["_preflight_pending"] = {
            "mode": "Single",
            "env": env,
            "knode": knode,
            "fqdn_base": stack["stack_fqdn_base"],
            "payload": payload,
            "admin_email": admin_email,
            "admin_password": admin_password,
        }
        st.session_state["_preflight_fingerprint"] = fp

    if st.session_state.get("_preflight_pending", {}).get("mode") == "Single":
        _preflight_confirm_section(st.session_state["_preflight_pending"])

    if st.session_state.get("_preflight_running_data", {}).get("mode") == "Single":
        pending = st.session_state.pop("_preflight_running_data")

        # Clear previous results before starting a new run
        st.session_state.pop("create_tenant_last_results", None)
        st.session_state.pop("create_tenant_artifact_path", None)

        st.warning("⏳ **Tenant provisioning typically takes about 5 to 10 minutes.** Please KEEP THIS TAB OPEN and DO NOT REFRESH — results will appear automatically when done.")
        try:
            with st.spinner(f"Checking tsh connectivity to {pending['knode']}..."):
                ping_knode(pending["knode"])
        except APIRequestError as e:
            st.error(f"**tsh preflight failed — provisioning aborted.**\n\n{e}\n\nPlease run `tsh login` to refresh your Teleport session and try again.")
            st.stop()
        with st.spinner(f"Running tenant provisioning steps on {pending['knode']}..."):
            result = _run_single(pending["knode"], stack, env, pending["payload"], pending["admin_email"], pending.get("admin_password", ""))

        st.session_state["create_tenant_last_results"] = [result]
        artifact_path = _save_artifact([result], env)
        st.session_state["create_tenant_artifact_path"] = str(artifact_path)

    if "create_tenant_last_results" in st.session_state:
        st.subheader("Results")
        results = st.session_state["create_tenant_last_results"]
        for i, r in enumerate(results):
            _display_result(r, i + 1)

        artifact_path = st.session_state.get("create_tenant_artifact_path")
        if artifact_path:
            st.caption(f"Auto-saved to `{artifact_path}`")
        results_json = json.dumps(results, indent=2)
        st.download_button(
            label="Download Results (JSON)",
            data=results_json,
            file_name=f"create_tenant_{env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )


# ── Batch mode ─────────────────────────────────────────────────────────────────
else:
    # Clear any stale Single preflight when switching modes
    if st.session_state.get("_preflight_pending", {}).get("mode") == "Single":
        _clear_preflight()
    st.subheader("Batch Tenant Definitions")
    st.markdown("""
Paste a JSON array. Each object requires: `hostname`, `orgName`, `adminEmail`, `custFName`, `custLName`.
Optional: `domains`, `orgDesc`, `country`, `location`, `state`, `industry`, `paid`, `seats`, `fed_ramp_tenant`.

```json
[
  {"hostname": "test-tenant-01", "orgName": "Test Org 1", "adminEmail": "you@netskope.com", "custFName": "John", "custLName": "Doe"},
  {"hostname": "test-tenant-02", "orgName": "Test Org 2", "adminEmail": "you@netskope.com", "custFName": "Jane", "custLName": "Smith"}
]
```
""")
    st.warning("⚠️ **Each tenant in a batch must have a unique `orgName`.** Reusing the same `orgName` across tenants can cause provisioner registration failures for subsequent tenants. Tip: match `orgName` to `hostname` to keep them distinct.")

    batch_input = st.text_area("Tenant JSON Array", height=200, placeholder='[{"hostname": "...", ...}]')
    admin_password = st.text_input(
        "Admin Password (optional)",
        placeholder="Leave blank to send verification email instead",
        type="password",
        help="If provided, the admin account is activated directly via SQL — no email click required. Leave blank to use the standard email verification flow.",
    )
    # Detect stale preflight before rendering the Run Batch button so it re-enables immediately
    if st.session_state.get("_preflight_pending", {}).get("mode") == "Batch":
        current_fp = _make_fingerprint({
            "mode": "Batch", "env": env, "knode": knode,
            "batch_input": batch_input.strip(), "has_password": bool(admin_password),
        })
        if current_fp != st.session_state.get("_preflight_fingerprint"):
            _clear_preflight()
            st.warning("Inputs changed after preflight review — please click Run Batch again to review the updated payload.")

    run_batch_clicked = st.button("Run Batch", type="primary", disabled=bool(st.session_state.get("_preflight_pending") or st.session_state.get("_preflight_running_data")))

    if run_batch_clicked:
        if not batch_input.strip():
            _clear_preflight()
            st.error("Please provide a JSON array of tenant definitions.")
            st.stop()
        try:
            tenant_defs = json.loads(batch_input)
        except json.JSONDecodeError as e:
            _clear_preflight()
            st.error(f"Invalid JSON: {e}")
            st.stop()
        if not isinstance(tenant_defs, list) or not tenant_defs:
            _clear_preflight()
            st.error("Input must be a non-empty JSON array.")
            st.stop()

        if admin_password and not db_credentials_file_exists():
            _clear_preflight()
            st.error("Admin Password is set but db_credentials.json is missing — copy src/config/db_credentials.json.example to db_credentials.json and fill in credentials.")
            st.stop()

        required_fields = {"hostname", "orgName", "adminEmail", "custFName", "custLName"}
        for i, td in enumerate(tenant_defs):
            missing = required_fields - set(td.keys())
            if missing:
                _clear_preflight()
                st.error(f"Tenant #{i+1} missing required fields: {missing}")
                st.stop()

        org_names = [td["orgName"] for td in tenant_defs]
        duplicate_org_names = {n for n in org_names if org_names.count(n) > 1}
        if duplicate_org_names:
            _clear_preflight()
            st.error(f"Duplicate `orgName` values detected: {', '.join(sorted(duplicate_org_names))} — each tenant must have a unique orgName to avoid web UI routing failures.")
            st.stop()

        payloads = [_build_payload(td, stack["stack_fqdn_base"]) for td in tenant_defs]
        admin_emails = [td["adminEmail"] for td in tenant_defs]
        fp = _make_fingerprint({
            "mode": "Batch", "env": env, "knode": knode,
            "batch_input": batch_input.strip(), "has_password": bool(admin_password),
        })
        st.session_state["_preflight_pending"] = {
            "mode": "Batch",
            "env": env,
            "knode": knode,
            "fqdn_base": stack["stack_fqdn_base"],
            "payloads": payloads,
            "admin_emails": admin_emails,
            "admin_password": admin_password,
        }
        st.session_state["_preflight_fingerprint"] = fp

    if st.session_state.get("_preflight_pending", {}).get("mode") == "Batch":
        _preflight_confirm_section(st.session_state["_preflight_pending"])

    if st.session_state.get("_preflight_running_data", {}).get("mode") == "Batch":
        pending = st.session_state.pop("_preflight_running_data")
        payloads = pending["payloads"]
        admin_emails = pending["admin_emails"]

        # Clear previous results before starting a new run
        st.session_state.pop("create_tenant_last_results", None)
        st.session_state.pop("create_tenant_artifact_path", None)

        st.warning(f"⏳ **Running {len(payloads)} tenant(s) sequentially — each takes 5–7 minutes.** Estimated total: {len(payloads) * 6}–{len(payloads) * 8} minutes. Keep this tab open and do not refresh.")
        try:
            with st.spinner(f"Checking tsh connectivity to {pending['knode']}..."):
                ping_knode(pending["knode"])
        except APIRequestError as e:
            st.error(f"**tsh preflight failed — batch aborted.**\n\n{e}\n\nPlease run `tsh login` to refresh your Teleport session and try again.")
            st.stop()

        results: list[dict[str, Any]] = []
        progress = st.progress(0, text="Starting...")
        status_placeholder = st.empty()

        # Step 1: Create all tenants
        create_results: list[dict[str, Any]] = []
        last_elapsed: float | None = None
        for i, payload in enumerate(payloads):
            fqdn = _build_fqdn(payload["hostname"], stack["stack_fqdn_base"])
            admin_email = admin_emails[i]
            prev_note = f" (prev took {_fmt_elapsed(last_elapsed)})" if last_elapsed is not None else ""
            status_placeholder.write(f"Step 1 [{i+1}/{len(payloads)}]: Creating `{fqdn}`...{prev_note}")
            r: dict[str, Any] = {
                "hostname": payload["hostname"],
                "admin_email": admin_email,
                "env": env,
                "knode": knode,
                "request_payload": payload,
                "steps": {},
                "tenant_id": None,
                "fqdn": fqdn,
                "overall_status": "incomplete",
            }
            t0 = time.time()
            try:
                data = create_tenant(knode, payload)
                r["steps"]["1_create_tenant"] = {"status": "ok", "response": data}
                r["tenant_id"] = (
                    data.get("tenantData", {}).get("TenantID")
                    or data.get("tenantId")
                    or data.get("tenant_id")
                    or data.get("orgId")
                )
                r["fqdn"] = (
                    data.get("tenantData", {}).get("ui_hostname")
                    or fqdn
                )
                step1_status = (data.get("status") or "").lower()
                if step1_status != "success":
                    msg = data.get("msg") or data.get("message") or "status is not 'success'"
                    r["steps"]["1_create_tenant"]["warning"] = msg
                    r["steps"]["1_create_tenant"]["remediation_steps"] = (
                        data.get("remediationSteps") or data.get("remediation_steps")
                    )
                    r["overall_status"] = "incomplete"
            except (APIRequestError, APIResponseError) as e:
                r["steps"]["1_create_tenant"] = {"status": "error", "error": str(e)}
                r["overall_status"] = "failed_at_step_1"
            if not r["tenant_id"] and r["overall_status"] != "failed_at_step_1":
                r["steps"]["1_create_tenant"].setdefault("warning", "tenant_id not found in response — skipping dependent steps")
                r["overall_status"] = "failed_at_step_1"
            last_elapsed = time.time() - t0
            r["elapsed_seconds"] = round(last_elapsed)
            create_results.append(r)
            progress.progress((i + 1) / (len(payloads) * 4), text=f"Created {i+1}/{len(payloads)}")

        # Step 2: Single cluster mapping refresh (only if at least one create succeeded)
        successful_creates = [r for r in create_results if r["tenant_id"] is not None]

        if not successful_creates:
            skip_note = "Skipped: no tenant creation succeeded."
            for r in create_results:
                r["steps"]["2_cluster_mapping"] = {"status": "skipped", "note": skip_note}
                r["steps"]["3_dns_sync"] = {"status": "skipped", "note": skip_note}
                r["steps"]["4a_get_admin_uuid"] = {"status": "skipped", "note": skip_note}
                r["steps"]["4b_send_verification_email"] = {"status": "skipped", "note": skip_note}
                if pending.get("admin_password", ""):
                    r["steps"]["5_activate_admin"] = {"status": "skipped", "note": skip_note}
                if r.get("overall_status") not in ("failed_at_step_1", "incomplete"):
                    r["overall_status"] = "failed"
            results = list(create_results)
        else:
            status_placeholder.write("Step 2: Refreshing cluster mapping (single call)...")
            try:
                cm_data = refresh_cluster_mapping(knode)
                cm_result = {"status": "ok", "response": cm_data}
            except (APIRequestError, APIResponseError) as e:
                cm_result = {"status": "error", "error": str(e)}

            progress.progress(2 / 4, text="Cluster mapping refreshed")

            # Step 3 + 4: Per-tenant DNS sync and email
            for i, r in enumerate(create_results):
                r["steps"]["2_cluster_mapping"] = cm_result
                if cm_result["status"] == "error":
                    r["overall_status"] = "failed_at_step_2"
                    results.append(r)
                    continue
                if r["overall_status"] == "failed_at_step_1":
                    results.append(r)
                    continue

                tenant_id = str(r["tenant_id"])
                fqdn = r["fqdn"]
                admin_email = r["admin_email"]

                # Step 3: DNS sync
                status_placeholder.write(f"Step 3 [{i+1}/{len(create_results)}]: DNS sync for `{fqdn}`...")
                try:
                    data = sync_dns(knode, fqdn, stack["gslb_home_pop"])
                    r["steps"]["3_dns_sync"] = {"status": "ok", "response": data}
                except (APIRequestError, APIResponseError) as e:
                    r["steps"]["3_dns_sync"] = {"status": "error", "error": str(e)}
                    r["overall_status"] = "failed_at_step_3"
                    results.append(r)
                    continue

                # Step 4a: Get admin UUID (cached per email)
                admin_uuid = st.session_state.get("_admin_uuid_cache", {}).get(admin_email)
                if not admin_uuid:
                    status_placeholder.write(f"Step 4a: Fetching admin UUID for `{admin_email}`...")
                    try:
                        admin_uuid = get_admin_uuid(knode, stack["ms_platform_fqdn"], admin_email, tenant_id)
                        if "_admin_uuid_cache" not in st.session_state:
                            st.session_state["_admin_uuid_cache"] = {}
                        st.session_state["_admin_uuid_cache"][admin_email] = admin_uuid
                        r["steps"]["4a_get_admin_uuid"] = {"status": "ok", "uuid": admin_uuid}
                    except (APIRequestError, APIResponseError) as e:
                        r["steps"]["4a_get_admin_uuid"] = {"status": "error", "error": str(e)}
                        r["overall_status"] = "failed_at_step_4a"
                        results.append(r)
                        continue
                else:
                    r["steps"]["4a_get_admin_uuid"] = {"status": "ok_cached", "uuid": admin_uuid}

                # Step 4b: Send verification email (skipped when admin_password is set)
                batch_password = pending.get("admin_password", "")
                if batch_password:
                    r["steps"]["4b_send_verification_email"] = {"status": "skipped", "note": "SQL activation will be used instead"}
                else:
                    status_placeholder.write(f"Step 4b [{i+1}/{len(create_results)}]: Sending verification email for tenant `{tenant_id}`...")
                    try:
                        data = send_verification_email(knode, stack["ms_platform_fqdn"], admin_uuid, tenant_id)
                        r["steps"]["4b_send_verification_email"] = {"status": "ok", "response": data}
                    except (APIRequestError, APIResponseError) as e:
                        err_str = str(e)
                        if "already verified" in err_str.lower():
                            r["steps"]["4b_send_verification_email"] = {"status": "already_verified", "note": err_str}
                        else:
                            r["steps"]["4b_send_verification_email"] = {"status": "error", "error": err_str}
                            r["overall_status"] = "failed_at_step_4b"
                            results.append(r)
                            continue

                # Step 5: Activate admin via SQL (auto-detects Postgres vs MariaDB path)
                if batch_password:
                    status_placeholder.write(f"Step 5 [{i+1}/{len(create_results)}]: Activating admin for tenant `{tenant_id}`...")
                    try:
                        data = _activate_admin(env, stack, admin_uuid, admin_email, r["hostname"], batch_password)
                        r["steps"]["5_activate_admin"] = {"status": "ok", "response": data}
                    except (APIRequestError, APIResponseError) as e:
                        r["steps"]["5_activate_admin"] = {"status": "error", "error": str(e)}
                        r["overall_status"] = "failed_at_step_5"
                        results.append(r)
                        continue

                step1_incomplete = "warning" in r["steps"].get("1_create_tenant", {})
                r["overall_status"] = "incomplete" if step1_incomplete else "success"
                results.append(r)

                progress.progress((2 + (i + 1) * 2) / (len(create_results) * 4 + 0.01), text=f"Completed {i+1}/{len(create_results)}")

        progress.progress(1.0, text="Done")
        status_placeholder.empty()

        st.session_state["create_tenant_last_results"] = results
        artifact_path = _save_artifact(results, env)
        st.session_state["create_tenant_artifact_path"] = str(artifact_path)

    if "create_tenant_last_results" in st.session_state:
        results = st.session_state["create_tenant_last_results"]
        st.subheader(f"Results ({len(results)} tenant(s))")

        success_count = sum(1 for r in results if r.get("overall_status") == "success")
        failed_count = len(results) - success_count
        col1, col2 = st.columns(2)
        col1.metric("Succeeded", success_count)
        col2.metric("Failed / Incomplete", failed_count)

        for i, r in enumerate(results):
            _display_result(r, i + 1)

        artifact_path = st.session_state.get("create_tenant_artifact_path")
        if artifact_path:
            st.caption(f"Auto-saved to `{artifact_path}`")
        results_json = json.dumps(results, indent=2)
        st.download_button(
            label="Download Results (JSON)",
            data=results_json,
            file_name=f"create_tenant_batch_{env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
