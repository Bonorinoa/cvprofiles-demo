"""Method screen — what the numbers mean, for a reader who has never seen this."""

import streamlit as st

st.title("How to read these numbers")

st.markdown(
    "You have a theory about how two constructs relate, and several candidate "
    "**measures** you could use for each. Not every measure is entitled to the "
    "interpretation you want to give it. This demo asks which ones survive."
)

st.markdown(
    "Everything the engine reads is yours: a **menu** of candidate measures, and a set "
    "of **restrictions** — observable implications your theory declares — each with a "
    "tightness **θ**."
)

st.markdown("### The four things on screen")

st.markdown(
    """
| Symbol | Name | What it is |
|---|---|---|
| `M*` | **Admissible set** | The measures that survive *every* restriction you declared. A set, not a winner. |
| `[L, U]` | **Identified range** | From the lowest to the highest β across the survivors. Not a confidence interval. |
| `θ` | **Tightness** | How demanding a restriction is. Raise it and the survivor set can only shrink. |
| `width` | `U − L` | The range you have not ruled out. |
"""
)

st.markdown(
    "**Admissible** means candidacy, not correctness: a measure that survives your "
    "restrictions is one you are *not yet entitled to reject*. The engine never picks a "
    "single best measure for you."
)

st.markdown("### `[L, U]` is not a confidence interval")

st.markdown(
    "A confidence interval says: the true value lies here with 95% probability. This "
    "range says something else. It runs from the **lowest to the highest value β takes "
    "across the measures that survived** — drawn by your restrictions, not by sampling "
    "noise. Values between the ends are not ruled out; the ends are what the survivors "
    "actually reach."
)

st.markdown("### A narrower range can be the worse answer")

st.markdown(
    "Cut the width to zero and you may have *removed a disagreement* rather than "
    "resolved one. If a narrow `[L, U]` comes from a single survivor, one side of a "
    "live dispute has been deleted — and the result is reported as if identified. The "
    "honest move is to arbitrate between the measures in tension, not to drop the "
    "inconvenient one."
)

st.markdown(
    "Related: many measures are **inert** — dropping them moves the range by exactly "
    "zero. They do no identifying work for this target."
)

st.markdown("### When nothing survives")

st.markdown(
    "An **empty `M*`** means no measure in your menu clears every restriction. This is "
    "a finding, not a crash: either your theory is too demanding for these measures, or "
    "one of them does not measure what it claims. The engine returns it as a result."
)

st.caption(
    "Every run on this site is **exploratory**. The package's provenance rule reserves "
    "the label *citable paper evidence* for runs with bootstrap, grids, and holdout "
    "enabled — none of which this demo turns on."
)
