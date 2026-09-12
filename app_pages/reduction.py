"""Reduction screen — which measurement is load-bearing?"""

import altair as alt
import pandas as pd
import streamlit as st

from core.engine import FIXTURES, leave_one_out, measures_of, width_of

INK = "#6b2c1f"

st.title("Which measurement is load-bearing?")

st.markdown(
    "Leave-one-out over the menu with the network and target functional held fixed. "
    "Dropping a measure that matters moves the range; dropping one that does not, "
    "changes nothing. Run at each fixture's pinned network."
)

label = st.segmented_control(
    "Dataset",
    options=[f.label for f in FIXTURES],
    default=FIXTURES[1].label,
    key="red_fixture",
)
fx = next((f for f in FIXTURES if f.label == label), FIXTURES[1])

data = leave_one_out(fx.key)
baseline = data["baseline"]
rows = [r for r in data["rows"] if r.get("ok")]

if not baseline.get("ok") or not rows:
    st.error("No usable runs — the baseline failed against this network.")
    st.stop()

base_w = width_of(baseline)

frame = pd.DataFrame(
    [
        {
            "label": r["label"],
            "L": r["L"],
            "U": r["U"],
            "width": width_of(r),
            "delta": None if width_of(r) is None else round(width_of(r) - base_w, 6),
            "survivors": len(r["M_star"]),
        }
        for r in rows
    ]
)

chart_bars = (
    alt.Chart(frame)
    .mark_bar(size=13, color=INK)
    .encode(
        x=alt.X(
            "L:Q",
            title="target functional β",
            scale=alt.Scale(zero=False, padding=24),
        ),
        x2="U:Q",
        y=alt.Y("label:N", title=None, sort=None),
        tooltip=["label", "L", "U", "width", "survivors"],
    )
)
# Degenerate rows (L == U) draw no bar, so mark the point explicitly — otherwise a
# collapsed interval reads as missing data rather than as a one-measure verdict.
chart_ticks = (
    alt.Chart(frame[frame["width"] == 0.0])
    .mark_tick(size=15, thickness=3, color=INK)
    .encode(x=alt.X("L:Q"), y=alt.Y("label:N", sort=None))
)
chart = (chart_bars + chart_ticks).properties(height=max(150, 34 * len(frame)))
st.altair_chart(chart, width="stretch")

st.dataframe(
    frame.rename(
        columns={
            "label": "case",
            "width": "range width",
            "delta": "Δ width",
            "survivors": "survivors",
        }
    ),
    hide_index=True,
    width="stretch",
)
st.caption(
    "`survivors` is the size of the admissible set M\\* — how many measures the "
    "conclusion rests on."
)

# ------------------------------------------------------------- interpretation
inert = frame[(frame["delta"].abs() < 1e-9) & (frame["label"] != "full menu")]
degenerate = frame[(frame["width"] == 0.0) & (frame["survivors"] == 1)]
drivers = frame[(frame["delta"] < -1e-9) & (frame["survivors"] == 1)]

if not inert.empty:
    st.markdown(
        f"**{len(inert)} of {len(frame) - 1} measures are inert here.** Dropping them "
        "changes the identified range by exactly zero: "
        f"{', '.join(inert['label'].tolist())}. They are not doing identifying work "
        "for this target — which is worth knowing before you collect more of them."
    )

if not drivers.empty:
    names = " or ".join(drivers["label"].tolist())
    st.warning(
        "**A narrower range is not automatically a better answer.** "
        f"Dropping {names} collapses the width to zero — but the survivor count drops "
        "to one. That is not a tighter estimate; it is the same disagreement with one "
        "side removed, reported as if it were identified. The honest move is to "
        "arbitrate between the measures in tension, not to delete the inconvenient one.",
        icon=":material/warning:",
    )

st.caption(
    "Each subset is a different validated input and therefore has a different run id. "
    "Exploratory — not citable paper evidence."
)
