import streamlit as st

__version__ = "2026.03"

st.set_page_config(page_title="Octo - Home", layout="wide")
st.title("🐙 Octo")
st.caption(f"v{__version__}")

st.write("SWG internal tooling for managing feature flags across environments.")
st.write("Use the sidebar to navigate between tools.")
