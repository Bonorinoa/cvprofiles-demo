"""Build network — author your own nomological network, and find its limits.

The pedagogy, in order:

1. read the pinned network as data rather than prose;
2. re-wire it — change a type, re-point a binding, tighten θ — and watch the verdict move;
3. meet the structural consequence: a restriction anchored to a **measure** costs you the
   reduction curve, because removing that measure orphans the restriction;
4. see the engine refuse rather than guess, which is the product, not a bug.

The page is a teaching instrument, so it deliberately lets the reader walk into the
consequence and then explains it. Hiding the trap would be easier and would teach nothing.
"""

import json

import altair as alt
import pandas as pd
import streamlit as st

from core.engine import (
    BY_KEY,
    FIXTURES,
    RESTRICTION_TYPES,
    STAGES,
    anchor_class,
    bindable_columns,
    default_restrictions,
    leave_one_out_custom,
    measures_of,
    network_to_yaml,
    rows_to_restrictions,
    run_custom,
    width_of,
)
from core.feedback import footer

INK = "#6b2c1f"

st.title("Build a network")

st.markdown(
    "A theory about how constructs relate implies things that must hold in the data. "
    "Written down, those become a **nomological network**: a list of restrictions, each "
    "saying *if the story is right, this must be true of these columns*. The engine then "
    "asks which of your candidate measures survive it."
)

# ------------------------------------------------------------------ seed + editor
label = st.segmented_control(
    "Dataset",
    options=[f.label for f in FIXTURES],
    default=FIXTURES[1].label,
    key="bn_fixture",
)
fx = next((f for f in FIXTURES if f.label == label), FIXTURES[1])
menu = measures_of(fx)
bindable = bindable_columns(fx)

PRESETS = ("Pinned network", "Anchored to a measure")
preset = st.segmented_control(
    "Start from",
    options=PRESETS,
    default=PRESETS[0],
    key="bn_preset_choice",
    help="The second preset walks you into the structural trap on purpose.",
)

seed = default_restrictions(fx)
if preset == PRESETS[1]:
    # The natural thing to write, and the thing that costs you the reduction curve.
    anchor_measure = menu[0]
    seed = seed + [
        {
            "type": "corr_min",
            "binds to": anchor_measure,
            "theta": 0.10,
            "id": "u_meas",
            "stage": "select",
            "sign": 1,
        }
    ]

# Re-seed the editor when the preset or dataset changes. Streamlit widgets own their
# state, so dropping the key is what forces it to re-initialise from `seed`.
if st.session_state.get("_bn_identity") != (fx.key, preset):
    st.session_state["_bn_identity"] = (fx.key, preset)
    st.session_state.pop("bn_editor", None)

with st.container(border=True):
    st.markdown("#### 1 · Re-wire the theory")
    st.caption(
        "Each row is one declared implication. Change a type, re-point what it binds to, "
        "or tighten θ — the verdict below re-computes. Add a restriction with the blank "
        "row at the bottom."
    )
    edited = st.data_editor(
        pd.DataFrame(seed),
        key="bn_editor",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "type": st.column_config.SelectboxColumn(
                "type",
                options=list(RESTRICTION_TYPES),
                required=True,
                width="medium",
                help="`stability` needs no column; the others bind to one.",
            ),
            "binds to": st.column_config.SelectboxColumn(
                "binds to",
                options=bindable,
                width="medium",
                help="Auxiliary columns are safe to bind. Binding to a *measure* has a "
                "consequence you will meet in step 3.",
            ),
            "theta": st.column_config.NumberColumn(
                "θ",
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                format="%.2f",
                width="small",
                help="Tightness. Raising it can only shrink the survivor set.",
            ),
            "id": st.column_config.TextColumn("id", width="small", required=True),
            "stage": st.column_config.SelectboxColumn(
                "stage", options=list(STAGES), width="small"
            ),
            "sign": st.column_config.SelectboxColumn(
                "sign", options=[1, -1], width="small", help="`monotone_rank` only."
            ),
        },
    )

restrictions = rows_to_restrictions(edited.to_dict("records"))
if not restrictions:
    st.info(
        "A network needs at least one complete restriction — a type, and the column it "
        "binds to where the type requires one.",
        icon=":material/pending:",
    )
    st.stop()

case = run_custom(fx.key, tuple(menu), json.dumps(restrictions, sort_keys=True))

# ------------------------------------------------------------------------ verdict
with st.container(border=True):
    st.markdown("#### 2 · What your network admits")

    if not case["ok"]:
        st.warning(
            "The engine refused this network rather than guessing. That is the boundary "
            "working — read the message, it names the row at fault.",
            icon=":material/block:",
        )
        st.code(f"{case['error']}: {case['detail']}", language="text")
    elif case["empty"]:
        st.warning(
            "**No measure survives your network.** Either the theory is more demanding "
            "than these measures can satisfy, or one of them does not measure what it "
            "claims. Changing which column a restriction binds to is often what decides "
            "which of those it is.",
            icon=":material/block:",
        )
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lower bound", f"{case['L']:.4f}")
        c2.metric("Upper bound", f"{case['U']:.4f}")
        c3.metric("Width", f"{width_of(case):.4f}")
        c4.metric("Admissible", f"{len(case['M_star'])} of {case['n_measures']}")

        span = pd.DataFrame([{"label": "identified range", "L": case["L"], "U": case["U"]}])
        st.altair_chart(
            alt.Chart(span)
            .mark_bar(size=18, color=INK)
            .encode(
                x=alt.X("L:Q", title="target functional β", scale=alt.Scale(zero=False, padding=24)),
                x2="U:Q",
                y=alt.Y("label:N", title=None, axis=None),
            )
            .properties(height=70),
            width="stretch",
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "measure": m,
                        "verdict": "admissible" if m in case["M_star"] else "rejected",
                        "failing": ", ".join(case["rejected"].get(m, [])) or "—",
                    }
                    for m in menu
                ]
            ),
            hide_index=True,
            width="stretch",
        )

# --------------------------------------------------- step 3: the consequence
with st.container(border=True):
    st.markdown("#### 3 · What your network costs you")

    anchored = [(r, anchor_class(r, menu)) for r in restrictions]
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "restriction": r["id"],
                    "type": r["type"],
                    "binds to": (r["params"] or {}).get("variable")
                    or (r["params"] or {}).get("group")
                    or (r["params"] or {}).get("ref_measure")
                    or "—",
                    "anchored to": kind,
                }
                for r, kind in anchored
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    on_measures = [r for r, kind in anchored if kind == "measure"]
    st.caption(
        "Reduction analysis removes each measure in turn. A restriction bound to an "
        "**auxiliary** column survives that; one bound to a **measure** does not."
    )

    if not on_measures:
        st.success(
            "Anchored to auxiliaries — the reduction curve is available. Try it.",
            icon=":material/check_circle:",
        )
        if st.button("Run the reduction curve on this network", icon=":material/compress:"):
            st.session_state["bn_run_reduction"] = True
        if st.session_state.get("bn_run_reduction"):
            loo = leave_one_out_custom(fx.key, json.dumps(restrictions, sort_keys=True))
            rows = [r for r in loo["rows"] if r.get("ok")]
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "case": r["label"],
                            "L": r["L"],
                            "U": r["U"],
                            "width": width_of(r),
                            "survivors": len(r["M_star"]),
                        }
                        for r in rows
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    else:
        pairs = ", ".join(
            f"`{r['id']}` → `{(r['params'] or {}).get('variable') or (r['params'] or {}).get('group') or (r['params'] or {}).get('ref_measure')}`"
            for r in on_measures
        )
        st.warning(
            f"**The reduction curve is no longer available for this network.** "
            f"Restriction {pairs} binds to a *measure* rather than an auxiliary column. "
            "Remove that measure and the restriction would point at a column that no "
            "longer exists — so the engine refuses rather than quietly dropping your "
            "theory.",
            icon=":material/link_off:",
        )
        loo = leave_one_out_custom(fx.key, json.dumps(restrictions, sort_keys=True))
        refused = [r for r in loo["rows"] if not r.get("ok")]
        if refused:
            st.markdown("Here is exactly what happens when you try:")
            st.code(
                "\n".join(
                    f"{r['label']:<22} {r['error']}: {r['detail'][:78]}" for r in refused
                ),
                language="text",
            )
            removals = [r for r in loo["rows"] if r.get("dropped")]
            ok_n = len(removals) - len(refused)
            st.caption(
                f"The other {ok_n} single-measure removals still run — the damage is "
                "specific to the measure your restriction names, not to the network as "
                "a whole."
            )
        st.info(
            "This is the trade. Binding to a measure makes the theory sharper and the "
            "analysis brittle. Binding to an auxiliary keeps the analysis free but asks "
            "less of the theory. Neither is wrong — but you should choose it on purpose.",
            icon=":material/lightbulb:",
        )

with st.expander("The network as the engine sees it"):
    st.caption("No hidden layer: this YAML is the whole specification.")
    st.code(network_to_yaml(restrictions), language="yaml")

footer("build-network")