import base64
import json

import requests
import streamlit as st

from api import APIRequestError, APIResponseError
from config.paths import BASE_DIR


with open(BASE_DIR / "config" / "stacks.json") as f:
    _env_config = json.load(f)

# session_state keys
#   webui_username                    — last used username (persisted)
#   webui_password                    — last used password (persisted)
#   webui_current_hostname            — hostname of the active session
#   webui_ci_session_{hostname}       — ci_session cookie per hostname


def _authenticate(hostname: str, username: str, password: str) -> str:
    session = requests.Session()

    try:
        token_resp = session.get(
            f"https://{hostname}/login/getToken",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not token_resp.ok:
        raise APIResponseError(token_resp.status_code, token_resp.text)

    csrf_hash = token_resp.json()["data"]
    csrf_token = base64.b64encode((csrf_hash + hostname).encode("ascii")).decode()

    try:
        auth_resp = session.post(
            f"https://{hostname}/login/authenticate",
            headers={
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            json={"username": username, "password": password, "token": csrf_token},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        raise APIRequestError(str(e)) from e

    if not auth_resp.ok:
        raise APIResponseError(auth_resp.status_code, auth_resp.text)

    ci_session = session.cookies.get("ci_session")
    if not ci_session:
        raise APIResponseError(auth_resp.status_code, "No ci_session cookie returned by authenticate endpoint")

    return ci_session


@st.dialog("Web UI Login")
def _login_dialog() -> None:
    env = st.selectbox("Environment", list(_env_config.keys()))
    stack_fqdn_base = _env_config[env]["stack_fqdn_base"]
    cache_key = f"tenants_{env}"

    # Prefer selecting from the cached tenant list if available
    if cache_key in st.session_state:
        st.text(f"Got tenant list for {env}, loaded from cache.")
        orgs = st.session_state[cache_key]["orgs"]
        hostnames = [o["ui_hostname"] for o in orgs if o.get("ui_hostname")]
        hostname = st.selectbox("Tenant", hostnames, help="Select your tenant from the list, or <backspace> and type tenant name to filter.")
    else:
        st.text(f"No tenant list cached for {env}. Please enter tenant name manually.")
        tenant_name = st.text_input(
            "Tenant name",
            placeholder="e.g. swg-mp-pdv-qa01",
            help=f"Short tenant name. Full hostname will be: <name>.{stack_fqdn_base}",
        )
        hostname = f"{tenant_name}.{stack_fqdn_base}" if tenant_name else ""
        if hostname:
            st.caption(f"Hostname: `{hostname}`")

    username = st.text_input("Username", value=st.session_state.get("webui_username", ""))
    password = st.text_input("Password", type="password", value=st.session_state.get("webui_password", ""))

    if st.button("Login", type="primary", disabled=not hostname):
        if not username or not password:
            st.error("Username and password are required.")
            return
        with st.spinner("Logging in..."):
            try:
                ci_session = _authenticate(hostname, username, password)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
                return
            except APIResponseError as e:
                st.error(f"Login failed ({e.status_code}): {e.body}")
                return

        st.session_state["webui_username"] = username
        st.session_state["webui_password"] = password
        st.session_state["webui_current_hostname"] = hostname
        st.session_state[f"webui_ci_session_{hostname}"] = ci_session
        st.rerun()


def webui_login_widget(sidebar: bool = False) -> str | None:
    """
    Renders a compact login status panel with a Login/Switch button.
    Opens a modal dialog for credentials when the button is clicked.

    Args:
        sidebar: When True, stacks status and button vertically (fits sidebar width).
                 When False (default), renders status and button side-by-side.

    Returns the active ci_session string, or None if not logged in.
    Pages can use the return value to gate further rendering:

        ci_session = webui_login_widget()
        if not ci_session:
            st.stop()
    """
    hostname = st.session_state.get("webui_current_hostname")
    ci_session = st.session_state.get(f"webui_ci_session_{hostname}") if hostname else None

    with st.container(border=True):
        if sidebar:
            if ci_session:
                username = st.session_state.get("webui_username", "")
                st.markdown("**Web UI Session** ")
                st.caption("✅ Logged in")
                st.caption(hostname)
                st.caption(username)
                if st.button("Switch", width="stretch"):
                    _login_dialog()
            else:
                st.markdown("**Web UI Session**")
                st.caption("Not logged in")
                if st.button("Login", type="primary", width="stretch"):
                    _login_dialog()
        else:
            col1, col2 = st.columns([3, 1])
            if ci_session:
                col1.markdown(f"**Web UI Session**  \n✅ `{hostname}`")
                if col2.button("Switch", width="stretch"):
                    _login_dialog()
            else:
                col1.markdown("**Web UI Session**  \n— Not logged in")
                if col2.button("Login", type="primary", width="stretch"):
                    _login_dialog()

    return ci_session
