import json
import streamlit as st
from api import APIRequestError, APIResponseError
from api.ris_base import (
    list_object_consumer,
    get_object_consumer_by_id,
    list_config_object,
    get_config_object_by_id,
)
from config.paths import BASE_DIR


def _flatten_consumer_list(elements: list) -> list[dict]:
    rows = []
    for el in elements:
        refs = el.get("references", [])
        ref_summary = "; ".join(
            f"{r['object_name']}: {', '.join(r['ids'])}" for r in refs
        ) if refs else ""
        rows.append({
            "setting_id": el.get("setting_id", ""),
            "references": ref_summary,
            "create_by": el.get("create_by", ""),
            "modify_by": el.get("modify_by", ""),
            "modify_time": el.get("modify_time", ""),
        })
    return rows


def _flatten_object_list(elements: list) -> list[dict]:
    rows = []
    for el in elements:
        refs = el.get("references", [])
        ref_summary = "; ".join(
            f"{r['consumer']}: {', '.join(r['id'])}" for r in refs
        ) if refs else ""
        rows.append({
            "id": el.get("id", ""),
            "references": ref_summary,
        })
    return rows


def _flatten_references(references: list) -> list[dict]:
    rows = []
    for ref in references:
        # Object consumer side: {object_name, ids}
        # Config object side:   {consumer, id}
        name = ref.get("object_name") or ref.get("consumer", "")
        ids = ref.get("ids") or ref.get("id", [])
        for rid in ids:
            rows.append({"name": name, "id": rid})
    return rows


with open(BASE_DIR / "config" / "stacks.json") as f:
    env_config = json.load(f)

st.set_page_config(page_title="Query RIS Reference", layout="wide")
st.title("Query RIS Reference")
st.markdown("""
Query **Referential Integrity Service (RIS)** to inspect reference relations between object consumers and config objects.

Use the **sidebar** to set the environment and tenant ID. Use **List** to browse all entries, then **Get** to drill into a specific ID's references.
""")

with st.sidebar:
    st.header("Controls")
    env = st.selectbox("Environment", list(env_config.keys()))
    klbi = env_config[env]["k8s_klbi"]
    tenant_id = st.text_input("Tenant ID", help="e.g. 9988")

# ── Main layout: two side-by-side sections ────────────────────────────────────
col_consumer, col_object = st.columns(2)

# ── Object Consumer ───────────────────────────────────────────────────────────
with col_consumer:
    st.subheader("Object Consumer")

    consumer_name = st.text_input("Consumer Name", key="consumer_name", help="Registered consumer name. e.g. rtp")
    consumer_id = st.text_input("Consumer ID", key="consumer_id", help="The ID (\"setting_id\") from List result to query its references.")
    btn_list_consumer, btn_get_consumer = st.columns(2)
    list_consumer_clicked = btn_list_consumer.button("List", key="list_consumer", width="stretch")
    get_consumer_clicked = btn_get_consumer.button("Get by ID", key="get_consumer", width="stretch")

    # ── Handle button clicks: fetch and store in session_state ────────────────
    if list_consumer_clicked:
        if not tenant_id:
            st.warning("Enter a Tenant ID in the sidebar.")
        elif not consumer_name:
            st.warning("Enter a Consumer Name.")
        else:
            try:
                with st.spinner("Fetching..."):
                    resp = list_object_consumer(klbi, tenant_id, consumer_name)
                data = resp.json()
                elements = data.get("elements", [])
                st.session_state["ris_consumer_list"] = {
                    "total": data.get("total_count", len(elements)),
                    "rows": _flatten_consumer_list(elements),
                }
                st.session_state.pop("ris_consumer_detail", None)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error {e.status_code}: {e.body}")

    if get_consumer_clicked:
        if not tenant_id:
            st.warning("Enter a Tenant ID in the sidebar.")
        elif not consumer_name:
            st.warning("Enter a Consumer Name.")
        elif not consumer_id:
            st.warning("Enter a Consumer ID.")
        else:
            try:
                with st.spinner("Fetching..."):
                    resp = get_object_consumer_by_id(klbi, tenant_id, consumer_name, consumer_id)
                data = resp.json()
                st.session_state["ris_consumer_detail"] = {
                    "caption": f"References for consumer **{consumer_name}** / ID **{consumer_id}**",
                    "rows": _flatten_references(data.get("references", [])),
                    "raw": data,
                }
                st.session_state.pop("ris_consumer_list", None)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error {e.status_code}: {e.body}")

    # ── Always render from session_state ──────────────────────────────────────
    if "ris_consumer_list" in st.session_state:
        result = st.session_state["ris_consumer_list"]
        st.caption(f"Total: **{result['total']}**")
        if result["rows"]:
            st.dataframe(result["rows"], width="stretch", hide_index=True)
        else:
            st.info("No entries found.")

    if "ris_consumer_detail" in st.session_state:
        result = st.session_state["ris_consumer_detail"]
        st.caption(result["caption"])
        if result["rows"]:
            st.dataframe(result["rows"], width="stretch", hide_index=True)
        else:
            st.info("No references found.")
        with st.expander("Full JSON"):
            st.json(result["raw"])

# ── Config Object ─────────────────────────────────────────────────────────────
with col_object:
    st.subheader("Config Object")

    object_name = st.text_input("Object Name", key="object_name", help="Registered config object name. e.g. destination")
    object_id = st.text_input("Object ID", key="object_id", help="The ID (\"id\") from List result to query its references.")
    btn_list_object, btn_get_object = st.columns(2)
    list_object_clicked = btn_list_object.button("List", key="list_object", width="stretch")
    get_object_clicked = btn_get_object.button("Get by ID", key="get_object", width="stretch")

    # ── Handle button clicks: fetch and store in session_state ────────────────
    if list_object_clicked:
        if not tenant_id:
            st.warning("Enter a Tenant ID in the sidebar.")
        elif not object_name:
            st.warning("Enter an Object Name.")
        else:
            try:
                with st.spinner("Fetching..."):
                    resp = list_config_object(klbi, tenant_id, object_name)
                data = resp.json()
                elements = data.get("elements", [])
                st.session_state["ris_object_list"] = {
                    "total": data.get("total_count", len(elements)),
                    "rows": _flatten_object_list(elements),
                }
                st.session_state.pop("ris_object_detail", None)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error {e.status_code}: {e.body}")

    if get_object_clicked:
        if not tenant_id:
            st.warning("Enter a Tenant ID in the sidebar.")
        elif not object_name:
            st.warning("Enter an Object Name.")
        elif not object_id:
            st.warning("Enter an Object ID.")
        else:
            try:
                with st.spinner("Fetching..."):
                    resp = get_config_object_by_id(klbi, tenant_id, object_name, object_id)
                data = resp.json()
                st.session_state["ris_object_detail"] = {
                    "caption": f"References for object **{object_name}** / ID **{object_id}**",
                    "rows": _flatten_references(data.get("references", [])),
                    "raw": data,
                }
                st.session_state.pop("ris_object_list", None)
            except APIRequestError as e:
                st.error(f"Request failed: {e}")
            except APIResponseError as e:
                st.error(f"API error {e.status_code}: {e.body}")

    # ── Always render from session_state ──────────────────────────────────────
    if "ris_object_list" in st.session_state:
        result = st.session_state["ris_object_list"]
        st.caption(f"Total: **{result['total']}**")
        if result["rows"]:
            st.dataframe(result["rows"], width="stretch", hide_index=True)
        else:
            st.info("No entries found.")

    if "ris_object_detail" in st.session_state:
        result = st.session_state["ris_object_detail"]
        st.caption(result["caption"])
        if result["rows"]:
            st.dataframe(result["rows"], width="stretch", hide_index=True)
        else:
            st.info("No references found.")
        with st.expander("Full JSON"):
            st.json(result["raw"])
