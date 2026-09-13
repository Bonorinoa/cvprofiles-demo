"""Run screen — adjust the inputs and watch the admissible set respond."""

import altair as alt
import pandas as pd
import streamlit as st

from core.engine import (
    BY_KEY,
    FIXTURES,
    measures_of,
    restrictions_of,
    run_case,
    width_of,
)

INK = "#6b2c1f"

st.title("Which of your measurements survive your own theory?")

st.markdown(
    "Most measurement choices are never tested before the data is collected. A theory "
    "about how two constructs relate implies things that must hold in the data — and "
    "those implications are checkable **before** you spend anything on the study."
)

st.markdown(
    "This runs that check. Choose which measures are in the running, and how demanding "
    "your theory is; the engine reports which ones survive and what that leaves "
    "identified."
)
st.page_link(
    "app_pages/method.py",
    label="Unfamiliar with the symbols? How to read this",
    icon=":material/menu_book:",
)

# ---------------------------------------------------------------- controls
with st.container(border=True):
    label = st.segmented_control(
        "Dataset",
        options=[f.label for f in FIXTURES],
        default=FIXTURES[1].label,
        key="run_fixture",
    )
    fx = next((f for f in FIXTURES if f.label == label), FIXTURES[1])
    st.caption(fx.blurb)

    menu = measures_of(fx)
    chosen = st.pills(
        "Measurement menu",
        options=menu,
        default=menu,
        selection_mode="multi",
        key="run_menu",
        help="Drop a measure and the engine re-identifies from what remains.",
    )

    rests = restrictions_of(fx)
    thetas: list[tuple[str, float]] = []
    if rests:
        st.caption("Restrictions — raise a θ and the surviving set can only shrink")
        cols = st.columns(min(len(rests), 3))
        for i, r in enumerate(rests):
            with cols[i % len(cols)]:
                t = st.slider(
                    f"{r['id']} · {r['type']}",
                    min_value=0.0,
                    max_value=1.0,
                    value=r["theta"],
                    step=0.05,
                    key=f"th_{fx.key}_{r['id']}",
                    help=f"stage: {r['stage']}",
                )
                thetas.append((r["id"], float(t)))

chosen = tuple(chosen or [])
if not chosen:
    st.warning("Keep at least one measure in the menu — an empty menu is not a profile.")
    st.stop()

case = run_case(fx.key, chosen, tuple(thetas))

if not case["ok"]:
    st.error(
        "The engine refused this input rather than guessing. That is a boundary, "
        f"not a crash — `{case['error']}`."
    )
    st.code(case["detail"], language="text")
    if "Restrict" in case["error"]:
        st.markdown(
            "A restriction or β still names a measure that is no longer in the menu. "
            "Either keep that measure, or edit the network so it binds only to "
            "columns that remain."
        )
    st.stop()

# ---------------------------------------------------------------- result
st.subheader("What remains identified")

if case["empty"]:
    st.info(
        "**No measure survives these assumptions.** The menu and the restrictions are "
        "incompatible — every candidate measure fails at least one declared implication. "
        "That is a result, not a failure: either the theory is too demanding for these "
        "measures, or one of them does not measure what it claims.",
        icon=":material/block:",
    )
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lower bound", f"{case['L']:.4f}")
    c2.metric("Upper bound", f"{case['U']:.4f}")
    c3.metric("Width", f"{width_of(case):.4f}")
    c4.metric("Admissible measures", f"{len(case['M_star'])} of {case['n_measures']}")

    span = pd.DataFrame(
        [{"label": "identified range", "L": case["L"], "U": case["U"]}]
    )
    chart = (
        alt.Chart(span)
        .mark_bar(size=18, color=INK)
        .encode(
            x=alt.X(
                "L:Q",
                title="target functional β",
                scale=alt.Scale(zero=False, padding=24),
            ),
            x2="U:Q",
            y=alt.Y("label:N", title=None, axis=None),
        )
        .properties(height=70)
    )
    st.altair_chart(chart, width="stretch")
    st.caption(
        "The bar is not a confidence interval. It is the range of conclusions your "
        "assumptions leave standing — the image of β over the measures that survive."
    )

frames = []
for m in chosen:
    if m in case["M_star"]:
        frames.append({"measure": m, "verdict": "admissible", "failing": "—"})
    else:
        frames.append(
            {
                "measure": m,
                "verdict": "rejected",
                "failing": ", ".join(case["rejected"].get(m, [])) or "—",
            }
        )
st.dataframe(pd.DataFrame(frames), hide_index=True, width="stretch")

with st.expander("Provenance"):
    st.caption(
        "Subsetting the menu changes the validated input, so it changes the run id. "
        "That is the contract working, not a broken freeze."
    )
    st.code(
        "\n".join(
            [
                f"run_id       {case['run_id'][:32]}…",
                f"scores_hash  {case['scores_hash'][:32]}…",
                f"network_hash {case['network_hash'][:32]}…",
                f"beta_hash    {case['beta_hash'][:32]}…",
                f"cvprofiles   {__import__('cvprofiles').__version__}",
            ]
        ),
        language="text",
    )

st.caption(
    "Exploratory. These runs are not citable paper evidence — the package's provenance "
    "rule requires the pinned freeze bundle."
)
