"""Failure-mode screen — watch the admissible set collapse to EMPTY.

The intellectual payload: raising a restriction's θ can only shrink the set of
measures that survive. When nothing survives, that is a designed, informative
outcome — a verdict about the research design obtained before any data money is
spent — not a crash.
"""

import pandas as pd
import streamlit as st

from core.engine import BY_KEY, measures_of, restrictions_of, run_case, width_of

INK = "#6b2c1f"

fx = BY_KEY["wvs_gps"]
menu = tuple(measures_of(fx))
rests = restrictions_of(fx)

st.title("When nothing survives")

st.markdown(
    "Raise a restriction's θ and the admissible set can only **shrink**. Drive it "
    "far enough on the flagship fixture and every measure dies. That is a *finding* "
    "about the research design — produced here, before any data-collection spend — "
    "not an error."
)

# ------------------------------------------------------------------ control
mult = st.slider(
    "Tightness multiplier — × θ, relative to the pinned network",
    min_value=1.0,
    max_value=3.0,
    value=1.0,
    step=0.1,
    key="fail_mult",
    help=(
        "Multiplies each restriction's pinned θ. The network is pinned at 1×; "
        "2.4× and above leave no measure standing."
    ),
)

thetas = tuple((r["id"], round(r["theta"] * mult, 3)) for r in rests)
st.caption("Resulting restrictions: " + " · ".join(f"{i}={v:.2f}" for i, v in thetas))

case = run_case(fx.key, menu, thetas)

if not case["ok"]:
    st.error(
        "The engine refused this input rather than guessing — that is a boundary, "
        f"not a crash. `{case['error']}`"
    )
    st.code(case["detail"], language="text")
    st.stop()

# ------------------------------------------------------------------ result
st.subheader("Result")

if case["empty"]:
    # The empty state is a designed result, not a crash. Stay calm, explain.
    st.warning(
        "**Nothing survives — and that is the answer, not a bug.** "
        "The theory is more demanding than these measures can satisfy, or at least "
        "one measure does not measure what its claim says it measures. This verdict "
        "was reachable before a single euro of data collection.",
        icon=":material/block:",
    )
    st.info(
        "Richard Hahn: *“it is useless to quantify uncertainty without a strategy "
        "to reduce it.”* An empty admissible set is precisely that warning made "
        "concrete — the identified interval has collapsed because the identifying "
        "assumptions and the measurement menu cannot hold together.",
        icon=":material/lightbulb:",
    )
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lower bound", f"{case['L']:.4f}")
    c2.metric("Upper bound", f"{case['U']:.4f}")
    c3.metric("Width", f"{width_of(case):.4f}")
    c4.metric("Admissible measures", f"{len(case['M_star'])} of {case['n_measures']}")

    frames = [
        {
            "measure": m,
            "verdict": "admissible" if m in case["M_star"] else "rejected",
            "failing": (
                "—"
                if m in case["M_star"]
                else ", ".join(case["rejected"].get(m, [])) or "—"
            ),
        }
        for m in menu
    ]
    st.dataframe(pd.DataFrame(frames), hide_index=True, width="stretch")

st.page_link(
    "app_pages/method.py",
    label="How to read this",
    icon=":material/menu_book:",
)
st.caption(
    "Exploratory — not citable paper evidence. Each tightness setting is a different "
    f"input to the engine and gets its own run id: `{case['run_id'][:20]}…`"
)
