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
            "app_pages/landing.py",
            title="Start here",
            icon=":material/home:",
            url_path="overview",
            default=True,
        ),
        st.Page(
            "app_pages/run.py",
            title="Which measures survive?",
            icon=":material/play_circle:",
            url_path="run",
        ),
        st.Page(
            "app_pages/reduction.py",
            title="What's load-bearing?",
            icon=":material/compress:",
            url_path="reduction",
        ),
        st.Page(
            "app_pages/build_network.py",
            title="Build your theory",
            icon=":material/account_tree:",
            url_path="build-network",
        ),
        st.Page(
            "app_pages/failure_mode.py",
            title="When nothing survives",
            icon=":material/block:",
            url_path="failure-mode",
        ),
        st.Page(
            "app_pages/method.py",
            title="How to read this",
            icon=":material/menu_book:",
            url_path="method",
        ),
    ]
)
pg.run()
