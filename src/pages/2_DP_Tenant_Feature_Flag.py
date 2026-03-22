import json
import streamlit as st
from api import APIRequestError, APIResponseError
from api.dp_tenant_feature_flag import get_dp_tenant_feature_flags, set_dp_tenant_feature_flag
from config.paths import BASE_DIR


with open(BASE_DIR / "config" / "stacks.json") as f:
    env_config = json.load(f)

# Setting page config and title
st.set_page_config(page_title="DP Tenant Feature Flag")
st.title("Manage DataPlane Tenant Feature Flags")
st.markdown("""
Use the **sidebar** to configure and manage DP tenant feature flags:

- **Get Feature Flags** — fetches all flags for a tenant at the DataPlane level. Optionally enter a _Feature Flag_ name to auto-filter the result.
- **Set Feature Flag** — sends a JSON body to update one or more DP tenant flags. The entire JSON object is submitted as the request body.
""")

with st.sidebar:
    st.header("Controls")

    env = st.selectbox("Environment", list(env_config.keys()))
    tenant_id = st.text_input("Tenant ID")
    desired_flag = st.text_input("Feature Flag keyword", help="Used to auto-filter results after Get. Not required for Set.")

    selected_stack = env_config[env]
    klbi = selected_stack["k8s_klbi"]

    get_clicked = st.button("Get Feature Flags")

    st.subheader("Set Feature Flag(s)")
    flag_body = st.text_area(
        "Input the whole JSON body:",
        height=200,
        placeholder='{\n    "cep-https-proxy": {\n        "enabled": true\n    }\n}',
        help="Input a valid JSON object. Each top-level key is a flag name, and its value is the flag configuration.",
    )
    set_clicked = st.button("Set Feature Flag")

# Get Feature Flag Logic
if get_clicked:
    # Clear previous get response when clicking the button again
    st.session_state.pop("dp_ff_get_response", None)

    if not tenant_id:
        st.error("Please enter a Tenant ID.")
        st.stop()

    try:
        with st.spinner(f"Calling API to get DP tenant feature flags for Tenant ID: {tenant_id}..."):
            response = get_dp_tenant_feature_flags(klbi, tenant_id)
    except APIRequestError as e:
        st.error(f"Request failed: {e}")
        st.stop()
    except APIResponseError as e:
        st.error(f"API error {e.status_code}: {e.body}")
        st.stop()

    st.session_state.dp_ff_get_response = {
        "env": env,
        "tenant_id": tenant_id,
        "status_code": response.status_code,
        "data": response.json(),
    }
    if desired_flag:
        st.session_state["dp_ff_search"] = desired_flag

if "dp_ff_get_response" in st.session_state:
    stored_resp_data = st.session_state.dp_ff_get_response
    st.write(f"### Get Feature Flag(s) Result:")
    st.write(f"- Stack Environment: {stored_resp_data['env']}")
    st.write(f"- Tenant ID: {stored_resp_data['tenant_id']}")
    st.caption(f"Status Code: {stored_resp_data['status_code']}")
    st.write("Raw Response Data: (expand to view)")
    st.json(stored_resp_data, expanded=False)

    search = st.text_input("Search flag...",
                           key="dp_ff_search",
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
    st.session_state.pop("dp_ff_set_response", None)

    if not tenant_id:
        st.error("Please enter a Tenant ID.")
        st.stop()
    if not flag_body.strip():
        st.error("Please enter a JSON body.")
        st.stop()

    try:
        flag_dict = json.loads(flag_body)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    if not isinstance(flag_dict, dict):
        st.error("JSON body must be an object (e.g. `{ \"flag-name\": { ... } }`).")
        st.stop()

    try:
        with st.spinner(f"Calling API to set DP tenant feature flag(s) for Tenant ID: {tenant_id}..."):
            response = set_dp_tenant_feature_flag(klbi, tenant_id, flag_dict)
    except APIRequestError as e:
        st.error(f"Request failed: {e}")
        st.stop()
    except APIResponseError as e:
        st.error(f"API error {e.status_code}: {e.body}")
        st.stop()

    st.session_state.dp_ff_set_response = {
        "env": env,
        "tenant_id": tenant_id,
        "body": flag_dict,
        "status_code": response.status_code,
        "data": response.json(),
    }

if "dp_ff_set_response" in st.session_state:
    stored_resp_data = st.session_state.dp_ff_set_response
    st.write(f"### Set Feature Flag Result:")
    st.write(f"- Stack Environment: {stored_resp_data['env']}")
    st.write(f"- Tenant ID: {stored_resp_data['tenant_id']}")
    st.write("Request Body Sent:")
    st.json(stored_resp_data["body"])
    st.caption(f"Status Code: {stored_resp_data['status_code']}")
    st.json(stored_resp_data["data"])
