import json
import streamlit as st
from api import APIRequestError, APIResponseError
from api.client_feature_flag import get_feature_flags, set_feature_flag
from config.paths import BASE_DIR


with open(BASE_DIR / "config" / "stacks.json") as f:
    env_config = json.load(f)

# Setting page config and title
st.set_page_config(page_title="Client Feature Flag")
st.title("Manage Client (Tenant) Feature Flags")
st.markdown("""
Use the **sidebar** to configure and manage feature flags:

- **Get Feature Flags** — fetches all flags for a tenant. Optionally enter a _Feature Flag_ name to auto-filter the result.
- **Set Feature Flag** — sets a specific flag to `0` (Disable), `1` (Enable) or a custom value for a tenant feature flag.
""")

with st.sidebar:
    st.header("Controls")

    env = st.selectbox("Environment", list(env_config.keys()))
    tenant_id = st.text_input("Tenant ID")
    desired_flag = st.text_input("Feature Flag")
    # flag_value = st.selectbox("Value", ["0", "1"])
    flag_value = st.text_input("Value", help="Enter 0 (Disable), 1 (Enable) or a value depending on the flag. All values are treated as strings by the API.")

    selected_stack = env_config[env]
    klbi = selected_stack["k8s_klbi"]

    get_clicked = st.button("Get Feature Flags")
    set_clicked = st.button("Set Feature Flag")

# Get Feature Flag Logic
if get_clicked:
    # Clear previous get response when clicking the button again
    st.session_state.pop("client_ff_get_response", None)

    if not tenant_id:
        st.error("Please enter a Tenant ID.")
        st.stop()

    try:
        with st.spinner(f"Calling API to get feature flags for Tenant ID: {tenant_id}..."):
            response = get_feature_flags(klbi, tenant_id)
    except APIRequestError as e:
        st.error(f"Request failed: {e}")
        st.stop()
    except APIResponseError as e:
        st.error(f"API error {e.status_code}: {e.body}")
        st.stop()

    st.session_state.client_ff_get_response = {
        "env": env,
        "tenant_id": tenant_id,
        "status_code": response.status_code,
        "data": response.json(),
    }
    if desired_flag:
        st.session_state["client_ff_search"] = desired_flag

if "client_ff_get_response" in st.session_state:
    stored_resp_data = st.session_state.client_ff_get_response
    st.write(f"### Get Feature Flag(s) Result:")
    st.write(f"- Stack Environment: {stored_resp_data['env']}")
    st.write(f"- Tenant ID: {stored_resp_data['tenant_id']}")
    st.caption(f"Status Code: {stored_resp_data['status_code']}")
    st.write("Raw Response Data: (expand to view)")
    st.json(stored_resp_data, expanded=False)

    search = st.text_input("Search flag...",
                           key="client_ff_search",
                           help="Enter a feature flag name to filter results, clear to show all.")
    flags_data = stored_resp_data["data"].get("data", stored_resp_data["data"])
    if search:
        flags_data = {
            k: v for k, v in flags_data.items() if search.lower() in k.lower()
        }
        st.text("Search results for Feature Flags:")
    st.json(flags_data)

# Set Feature Flag Logic
if set_clicked:
    # Clear previous set response when clicking the button again
    st.session_state.pop("client_ff_set_response", None)

    if not tenant_id:
        st.error("Please enter a Tenant ID.")
        st.stop()
    if not desired_flag:
        st.error("Please enter a Feature Flag name.")
        st.stop()
    if not flag_value:
        st.error("Please enter a Value for the Feature Flag.")
        st.stop()

    try:
        with st.spinner(f"Calling API to set feature flag '{desired_flag}' for Tenant ID: {tenant_id}..."):
            response = set_feature_flag(klbi, tenant_id, desired_flag, flag_value)
    except APIRequestError as e:
        st.error(f"Request failed: {e}")
        st.stop()
    except APIResponseError as e:
        st.error(f"API error {e.status_code}: {e.body}")
        st.stop()

    st.session_state.client_ff_set_response = {
        "env": env,
        "tenant_id": tenant_id,
        "flag": desired_flag,
        "value": flag_value,
        "status_code": response.status_code,
        "data": response.json(),
    }

if "client_ff_set_response" in st.session_state:
    stored_resp_data = st.session_state.client_ff_set_response
    st.write(f"### Set Feature Flag Result:")
    st.write(f"- Stack Environment: {stored_resp_data['env']}")
    st.write(f"- Tenant ID: {stored_resp_data['tenant_id']}")
    st.write(f"- Feature Flag: **{stored_resp_data['flag']}**")
    st.write(f"- Value: **{stored_resp_data['value']}**")
    st.caption(f"Status Code: {stored_resp_data['status_code']}")
    st.json(stored_resp_data["data"])
