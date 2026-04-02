import streamlit as st

pg = st.navigation({
    "": [
        st.Page("pages/home.py", title="Home"),
    ],
    "Tenant Info & Feature Flags": [
        st.Page("pages/show_tenant_list.py", title="Show Tenant List"),
        st.Page("pages/client_feature_flag.py", title="Client Feature Flag"),
        st.Page("pages/dp_tenant_feature_flag.py", title="DP Tenant Feature Flag"),
    ],
    "SWG Management Plane": [
        st.Page("pages/manage_api_token.py", title="Manage API Token"),
        st.Page("pages/query_ris_reference.py", title="Query RIS Reference"),
    ],
})

pg.run()
