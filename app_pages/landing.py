"""Start here — the claim, one real result, and the doors.

Deliberately NOT an architecture tour. A visitor arriving from elsewhere needs to know
in about ten seconds whether this is their problem, see one result that is actually
true, and find the door they want. Architecture belongs one screen down, in three
short steps; the symbols belong on "How to read this".

The headline number is COMPUTED at render time from the real engine rather than typed
into the copy, so this page cannot drift away from what the tool actually does. If the
computation fails, the page says so instead of showing a stale claim.
"""

import altair as alt
import pandas as pd
import streamlit as st

from core.engine import BY_KEY, leave_one_out, measures_of, width_of
from core.feedback import footer

INK = "#6b2c1f"
FX_KEY = "wvs_gps"

st.title("Does your measurement measure what you claim?")

st.markdown(
    "Most measurement choices are never tested before the data is collected. A theory "
    "about how constructs relate implies things that must hold in the data — and those "
    "implications are checkable **before** you spend anything on the study."
)

# ------------------------------------------------------- the proof, computed live
fx = BY_KEY[FX_KEY]
loo = leave_one_out(FX_KEY)
baseline = loo["baseline"]
removals = [r for r in loo["rows"] if r.get("ok") and r.get("dropped")]
base_w = width_of(baseline)

if baseline.get("ok") and removals and base_w is not None:
    inert = [r for r in removals if abs((width_of(r) or 0.0) - base_w) < 1e-9]
    collapse = [r for r in removals if len(r["M_star"]) == 1]
    n_measures = len(measures_of(fx))

    st.markdown("### A real result, computed here")
    st.markdown(
        f"Take a published fixture — {fx.blurb.split('.')[0].lower()} — and ask which of "
        f"its {n_measures} candidate measures survive a small set of declared "
        f"implications. Then remove each measure in turn and re-run:\n\n"
        f"**{len(inert)} of the {n_measures} are inert.** Dropping any of them moves the "
        f"identified range by *exactly zero*. The whole range comes from the two "
        f"remaining measures, and they disagree."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lower bound", f"{baseline['L']:.4f}")
    c2.metric("Upper bound", f"{baseline['U']:.4f}")
    c3.metric("Width", f"{base_w:.4f}")
    c4.metric("Admissible", f"{len(baseline['M_star'])} of {n_measures}")

    span = pd.DataFrame(
        [{"label": "identified range", "L": baseline["L"], "U": baseline["U"]}]
    )
    st.altair_chart(
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
        .properties(height=70),
        width="stretch",
    )
    st.caption(
        "Not a confidence interval. From the lowest to the highest value β takes "
        "across the measures that survived."
    )

    if collapse:
        st.markdown(
            "**You can make the range collapse to zero by deleting one measure** — "
            + ", ".join(f"`{r['dropped']}`" for r in collapse)
            + " — but that leaves a single survivor. A narrower range bought by removing "
            "one side of a disagreement is not a tighter answer."
        )
else:
    st.info(
        "The live computation did not return a usable baseline, so no numbers are shown. "
        "Better an obvious gap than a stale claim.",
        icon=":material/report:",
    )

# -------------------------------------------------------------- how it works
st.markdown("### How it works")
s1, s2, s3 = st.columns(3)
with s1:
    st.markdown("**01 · Declare**")
    st.caption(
        "A menu of candidate measures, and a small set of restrictions — observable "
        "implications your theory says must hold."
    )
with s2:
    st.markdown("**02 · Ask who survives**")
    st.caption(
        "The engine reports the admissible set M\\*: the measures still entitled to "
        "the interpretation you want. A set, not a winner."
    )
with s3:
    st.markdown("**03 · See what that leaves**")
    st.caption(
        "The identified range [L, U] is the span of conclusions those survivors still "
        "permit. Raise a restriction and the set can only shrink."
    )

st.page_link(
    "app_pages/method.py",
    label="How to read the symbols",
    icon=":material/menu_book:",
)

# ------------------------------------------------------------------- the doors
st.markdown("### Try it")
d1, d2 = st.columns(2)
with d1:
    st.page_link(
        "app_pages/run.py",
        label="Which measures survive?",
        icon=":material/play_circle:",
        help="Set the menu and the theory, see the verdict.",
    )
    st.page_link(
        "app_pages/reduction.py",
        label="What's load-bearing?",
        icon=":material/compress:",
        help="Remove each measure and see what moves.",
    )
with d2:
    st.page_link(
        "app_pages/build_network.py",
        label="Build your theory",
        icon=":material/account_tree:",
        help="Write your own network and find its limits.",
    )
    st.page_link(
        "app_pages/failure_mode.py",
        label="When nothing survives",
        icon=":material/block:",
        help="Drive a theory until every measure fails.",
    )

# --------------------------------------------------------------------- limits + vision
with st.expander("What this is not, and where it is going"):
    st.markdown(
        "- **Not a confidence interval.** The range comes from your assumptions, not "
        "from sampling noise.\n"
        "- **Not an estimator.** It reports what your assumptions leave standing; it "
        "does not pick a measure for you.\n"
        "- **Not citable evidence.** Every run here is exploratory. The underlying "
        "package reserves the label *citable* for runs with bootstrap, grids and "
        "holdout enabled, none of which this demo turns on.\n"
        "- **Not a product yet.** It is a working demonstration of one idea: that a "
        "measurement claim can be tested against the theory that entitles it *before* "
        "the data is bought."
    )
    st.markdown(
        "The longer bet is a library of such checks — frozen criteria, a portable "
        "evidence pack, a reduction strategy rather than another uncertainty number. "
        "That is a hypothesis, not a moat. This page is the first working instance."
    )

footer("overview")
