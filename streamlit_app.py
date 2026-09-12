"""cvprofiles — interactive demo.

Change the assumptions, watch the conclusion move. A thin UI over the published
``cvprofiles`` package; the engine is never reimplemented here.
"""

import streamlit as st

st.set_page_config(
    page_title="cvprofiles — interactive",
    page_icon=":material/account_tree:",
    layout="wide",
)

pg = st.navigation(
    [
        st.Page(
            "app_pages/run.py",
            title="Run",
            icon=":material/play_circle:",
            url_path="run",
            default=True,
        ),
        st.Page(
            "app_pages/reduction.py",
            title="Reduction",
            icon=":material/compress:",
            url_path="reduction",
        ),
    ]
)
pg.run()
