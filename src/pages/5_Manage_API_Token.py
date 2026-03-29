from datetime import datetime

import streamlit as st
from api import APIRequestError, APIResponseError
from api.scim_me import generate_api_token, get_scim_me, revoke_api_token
from components.webui_login import webui_login_widget


def _to_local(utc_str: str) -> str:
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

NETSKOPE_USER_KEY = "urn:ietf:params:scim:schemas:netskope:2.0:User"

st.set_page_config(page_title="Manage Tenant API Token", layout="wide")
st.title("Manage API Token")
st.markdown("Generate or revoke the API token for the logged-in user on a tenant web UI.")

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    webui_login_widget(sidebar=True)

    ci_session = st.session_state.get(
        f"webui_ci_session_{st.session_state.get('webui_current_hostname')}"
    )
    hostname = st.session_state.get("webui_current_hostname")
    generated_token_key = f"webui_generated_token_{hostname}"

    if ci_session:
        st.divider()

        # ── Generate ──────────────────────────────────────────────────────────

        st.subheader("Generate Token")
        expire_in_days = st.number_input(
            "Expires in (days)",
            min_value=1,
            max_value=3650,
            value=365,
            help="Number of days from now until the token expires.",
        )
        if st.button("Generate Token", type="primary", width="stretch"):
            try:
                with st.spinner("Generating..."):
                    gen_resp = generate_api_token(hostname, ci_session, expire_in_days=expire_in_days)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error ({e.status_code}): {e.body}")
            else:
                gen_data = gen_resp.json()
                new_token = gen_data.get(NETSKOPE_USER_KEY, {}).get("apiAccessToken", {}).get("value")
                st.session_state[generated_token_key] = new_token
                st.rerun()

        st.divider()

        # ── Revoke ────────────────────────────────────────────────────────────

        st.subheader("Revoke Token")
        st.caption("Immediately invalidates the active token. Any services using it will stop working.")
        if st.button("Revoke Token", type="secondary", width="stretch"):
            try:
                with st.spinner("Revoking..."):
                    revoke_resp = revoke_api_token(hostname, ci_session)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error ({e.status_code}): {e.body}")
            else:
                revoked_ns_user = revoke_resp.json().get(NETSKOPE_USER_KEY, {})
                if "apiAccessToken" not in revoked_ns_user:
                    st.session_state.pop(generated_token_key, None)
                    st.success("Token revoked.")
                else:
                    st.error("Revoke completed but token still appears in response. Please verify manually.")
                st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────

if not ci_session:
    st.info("Log in using the sidebar to continue.")
    st.stop()

# ── Current token status ──────────────────────────────────────────────────────

st.subheader("Current Status")

try:
    me_resp = get_scim_me(hostname, ci_session)
except APIRequestError as e:
    st.error(f"Request failed: {e}")
    st.stop()
except APIResponseError as e:
    st.error(f"API error ({e.status_code}): {e.body}")
    st.stop()

me = me_resp.json()
ns_user = me.get(NETSKOPE_USER_KEY, {})
token_info = ns_user.get("apiAccessToken")

col1, col2, col3 = st.columns(3)
col1.metric("User", me.get("userName", "—"))
col2.metric("Role", ns_user.get("role", {}).get("display", "—"))
col3.metric("Token Status", "Active" if token_info else "None")

if token_info:
    col_a, col_b = st.columns(2)
    issued_on = token_info.get("issuedOn")
    expires_on = token_info.get("expiresOn")
    col_a.metric("Issued On", _to_local(issued_on) if issued_on else "—")
    col_b.metric("Expires On", _to_local(expires_on) if expires_on else "—")

# ── New token banner ──────────────────────────────────────────────────────────

if generated_token_key in st.session_state:
    st.divider()
    st.subheader("New Token Generated")
    st.error(
        "⚠️ **Copy this token now.** ⚠️ "
        "This is the only time it will ever be shown — it cannot be retrieved again after this. "
        "Refreshing or leaving this page will permanently wipe it from view."
    )
    st.code(st.session_state[generated_token_key], language=None)
