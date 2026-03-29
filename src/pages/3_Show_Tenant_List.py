import json
import streamlit as st
import pandas as pd
from api import APIRequestError, APIResponseError
from api.get_all_tenants_in_stack import get_all_tenants_in_stack
from config.paths import BASE_DIR


with open(BASE_DIR / "config" / "stacks.json") as f:
    env_config = json.load(f)

st.set_page_config(page_title="Show Tenant List", layout="wide")
st.title("Show Tenant List")
st.markdown("""
Use the **sidebar** to select an environment and load the tenant list. Loaded data is cached for the session — click **Load Tenants** again to refresh.

Use the filter box to search tenants by **Tenant ID**, **name**, **hostname**, or **description**.
""")

with st.sidebar:
    st.header("Controls")
    env = st.selectbox("Environment", list(env_config.keys()))
    selected_stack = env_config[env]
    klbi = selected_stack["k8s_klbi"]
    load_clicked = st.button("Load Tenants")

cache_key = f"tenants_{env}"

if load_clicked:
    try:
        with st.spinner(f"Loading tenant list for {env}... (this may take a few seconds)"):
            response = get_all_tenants_in_stack(klbi)
    except APIRequestError as e:
        st.error(f"Request failed: {e}")
        st.stop()
    except APIResponseError as e:
        st.error(f"API error {e.status_code}: {e.body}")
        st.stop()

    data = response.json()
    st.session_state[cache_key] = {
        "env": env,
        "status_code": response.status_code,
        "orgs": data.get("orgs", []),
    }

if cache_key in st.session_state:
    cached = st.session_state[cache_key]
    orgs = cached["orgs"]
    total = len(orgs)

    col1, col2 = st.columns(2)
    col1.metric("Total Tenants", total)

    search = st.text_input(
        "Filter tenants...",
        help="Filter by Tenant ID, name, hostname, or description.",
    )

    filtered = orgs
    if search:
        s = search.lower()
        filtered = [
            o for o in orgs
            if s in str(o.get("TenantID", "")).lower()
            or s in (o.get("name") or "").lower()
            or s in (o.get("ui_hostname") or "").lower()
            or s in (o.get("description") or "").lower()
        ]
        st.caption(f"Showing **{len(filtered)}** of **{total}** tenants")

    df = pd.DataFrame(filtered)
    if not df.empty:
        if "pop" in df.columns:
            df["pop"] = df["pop"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

        preferred_cols = [
            "TenantID", "name", "ui_hostname", "description",
            "hashkey", "TenantIDHash", "create_time",
        ]
        cols = [c for c in preferred_cols if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

        if search:
            st.subheader("Filtered Tenant(s) — Full Detail")
            st.json(filtered)
    else:
        st.info("No tenants match the filter.")
else:
    st.info("Select an environment and click **Load Tenants** to begin.")
